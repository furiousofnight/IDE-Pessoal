from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
from ai.agent import IAAgentHybrid
from settings.user_settings import UserSettings
from chat.history import ChatHistory
import logging
from werkzeug.exceptions import HTTPException
import re
import bleach  # Biblioteca para sanitização HTML
import secrets  # Para geração de tokens seguros

# Configuração de logging mais detalhada
import logging
from logging.handlers import RotatingFileHandler

# Configuração do logger raiz
logging.basicConfig(
    level=logging.DEBUG,  # Captura todos os níveis de log
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            'hybrid_ide.log',
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5
        )
    ]
)

# Configurações específicas para loggers do projeto
logger = logging.getLogger("hybrid_ide_api")
logger.setLevel(logging.DEBUG)

# Logger para o agente de IA
ai_logger = logging.getLogger("hybrid_ide_ai")
ai_logger.setLevel(logging.DEBUG)

# Reduzir verbosidade de bibliotecas externas
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('flask_cors').setLevel(logging.WARNING)
logging.getLogger('flask_limiter').setLevel(logging.WARNING)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '../frontend'))
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, 'templates')
LLAMA2_CHAT_PATH = os.path.join(BASE_DIR, '../model/llama-2-7b-chat.Q4_K_M.gguf')
STABLE_CODE_PATH = os.path.join(BASE_DIR, '../model/stable-code-3b.Q8_0.gguf')

# 🔧 Corrigido: agora o static_folder aponta para a pasta frontend inteira
app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=FRONTEND_DIR)

# Configurações de segurança e performance
app.config['JSON_SORT_KEYS'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

# CORS configurado com opções de segurança
CORS(app, resources={
    r"/api/*": {"origins": ["http://localhost:5000", "http://127.0.0.1:5000"]}
})

# Rate limiting configurado por endpoint
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Inicialização dos componentes com tratamento de erros
try:
    hybrid_agent = IAAgentHybrid(LLAMA2_CHAT_PATH, STABLE_CODE_PATH)
    user_settings = UserSettings()
    chat_history = ChatHistory()
except Exception as e:
    logger.error(f"Erro na inicialização dos componentes: {e}")
    raise


def validate_json_payload(f):
    """Middleware simples para validar payload JSON."""
    def wrapper(*args, **kwargs):
        if not request.is_json:
            return jsonify(error="Payload deve ser JSON."), 400
        try:
            request.get_json(force=True)
        except Exception:
            return jsonify(error="JSON inválido."), 400
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def sanitize_input(input_string):
    """Sanitiza entradas para prevenir injeção e ataques."""
    if not isinstance(input_string, str):
        return ''
    input_string = re.sub(r'[\x00-\x1F\x7F]', '', input_string)
    input_string = input_string[:2000]
    return bleach.clean(input_string, strip=True)


def validate_filename(filename):
    """Valida e sanitiza nomes de arquivo."""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = filename[:255]
    return filename or 'arquivo_gerado.txt'


@app.after_request
def security_headers(response):
    """Adiciona headers de segurança em todas as respostas."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


@app.route("/")
def index():
    return render_template("index.html")


# 🔧 Corrigido: rota simplificada para servir arquivos estáticos
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.errorhandler(Exception)
def handle_exception(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    logger.error(f"Erro interno: {str(e)}")
    return jsonify(error="Ocorreu um erro inesperado no servidor. Tente novamente mais tarde."), code


@app.route("/api/ping")
def ping():
    return {"result": "pong"}


@app.route("/api/chat", methods=["POST"])
@limiter.limit("10/minute")
@validate_json_payload
def chat_api():
    try:
        data = request.get_json()
        user_msg = sanitize_input(data.get('message', ''))
        if not user_msg.strip():
            return jsonify(error="Mensagem inválida."), 400

        force_new = bool(data.get('force_new', False))
        reply, code, code_type = hybrid_agent.reply_chat(user_msg, force_new=force_new)

        reply = sanitize_input(reply) if reply else ''
        code = sanitize_input(code) if code else None

        if (not reply or reply.startswith('Erro:')) and not code:
            return jsonify(error="Não foi possível processar a solicitação."), 200

        chat_history.add_message(user_msg, "user")
        chat_history.add_message(reply, "assistant")
        if code:
            chat_history.add_message(code, "code")

        return jsonify(result=reply, code=code, code_type=code_type)
    except ValueError as e:
        logger.error(f"Erro de JSON na rota /api/chat: {str(e)}")
        return jsonify(error="Formato de dados inválido."), 400
    except Exception as e:
        logger.error(f"Erro na rota /api/chat: {str(e)}")
        return jsonify(error="Falha ao processar mensagem. Tente novamente mais tarde."), 500


@app.route("/api/status")
def status():
    chat_ready = (hybrid_agent.models.get('chat', None) is not None)
    code_ready = (hybrid_agent.models.get('code', None) is not None)
    return jsonify({
        "ia_chat_online": chat_ready,
        "ia_code_online": code_ready,
        "status": (chat_ready and code_ready)
    }), 200


@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(FRONTEND_DIR, 'favicon.ico', mimetype='image/x-icon')
    except FileNotFoundError:
        from flask import Response
        return Response('', status=204, mimetype='image/x-icon')


@app.route("/api/chat/history")
def get_chat_history():
    try:
        history_raw = chat_history.get_history()
        history = []
        for msg in history_raw:
            tipo = msg.get('role', msg.get('tipo', 'user'))
            mensagem = msg.get('content', msg.get('mensagem', ''))
            history.append({'tipo': tipo, 'mensagem': mensagem})
        return jsonify({"history": history}), 200
    except Exception as e:
        logger.error(f"Erro ao recuperar histórico: {str(e)}")
        return jsonify(error="Falha ao recuperar histórico."), 500


@app.route("/api/chat/clear", methods=["POST"])
@validate_json_payload
def clear_chat_history():
    try:
        chat_history.clear()
        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(f"Erro ao limpar histórico: {str(e)}")
        return jsonify(error="Falha ao limpar histórico."), 500


@app.route('/robots.txt')
def robots():
    from flask import Response
    return Response('User-agent: *\nDisallow:', status=200, mimetype='text/plain')


@app.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        return jsonify(user_settings.settings), 200
    except Exception as e:
        logger.error(f"Erro ao obter configurações: {str(e)}")
        return jsonify(error="Erro ao carregar configurações."), 500


@app.route("/api/settings", methods=["POST"])
def update_settings():
    try:
        data = request.get_json()
        if not data:
            return jsonify(error="Dados não recebidos."), 400
        for key, value in data.items():
            user_settings.set(key, value)
        if user_settings.save_settings():
            return jsonify(success=True, message="Configurações salvas com sucesso."), 200
        else:
            return jsonify(error="Erro ao salvar configurações."), 500
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações: {str(e)}")
        return jsonify(error="Erro ao atualizar configurações."), 500


@app.route("/api/settings/theme", methods=["POST"])
def update_theme():
    try:
        data = request.get_json()
        theme = data.get('theme', 'dark')
        if user_settings.update_theme(theme):
            return jsonify(success=True, theme=theme), 200
        else:
            return jsonify(error="Tema inválido."), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar tema: {str(e)}")
        return jsonify(error="Erro ao atualizar tema."), 500


@app.route("/api/settings/workspace", methods=["POST"])
def update_workspace():
    try:
        data = request.get_json()
        action = data.get('action')

        if action == 'add_file':
            file_path = data.get('file_path')
            if file_path and user_settings.add_recent_file(file_path):
                return jsonify(success=True), 200
            else:
                return jsonify(error="Erro ao adicionar arquivo."), 400

        elif action == 'add_favorite':
            template_name = data.get('template_name')
            if template_name and user_settings.add_favorite_template(template_name):
                return jsonify(success=True), 200
            else:
                return jsonify(error="Erro ao adicionar favorito."), 400

        return jsonify(error="Ação inválida."), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar workspace: {str(e)}")
        return jsonify(error="Erro ao atualizar workspace."), 500


@app.route("/api/clear_prompt_cache", methods=["POST"])
@validate_json_payload
def clear_prompt_cache():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        if not prompt.strip():
            return jsonify(error="Prompt não informado."), 400
        hybrid_agent.clear_prompt_cache(prompt)
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Erro ao limpar cache do prompt: {str(e)}")
        return jsonify(error="Falha ao limpar cache."), 500


@app.route("/api/save_code", methods=["POST"])
@validate_json_payload
def save_code():
    try:
        data = request.get_json()
        code = sanitize_input(data.get('code', ''))
        filename = validate_filename(data.get('filename', ''))

        if not code.strip():
            return jsonify(error="Código vazio ou inválido."), 400

        if not any(filename.endswith(ext) for ext in ['.html', '.css', '.js', '.py', '.txt']):
            filename += '.txt'

        if len(code) > 100000:
            return jsonify(error="Código muito grande."), 413

        save_dir = os.path.join(BASE_DIR, '../resultados-modelo')
        os.makedirs(save_dir, exist_ok=True)

        unique_filename = f"{secrets.token_hex(8)}_{filename}"
        file_path = os.path.join(save_dir, unique_filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        logger.info(f"Código salvo com segurança: {unique_filename}")
        return jsonify(success=True, file_path=file_path)
    except Exception as e:
        logger.error(f"Erro de segurança ao salvar código: {e}")
        return jsonify(error="Operação não autorizada."), 403


if __name__ == "__main__":
    import colorama
    colorama.init()

    def cleanup():
        try:
            if hybrid_agent and hybrid_agent.models:
                logger.info("Descarregando modelos...")
                for model_type, model in hybrid_agent.models.items():
                    if model:
                        try:
                            model.reset()
                            del model
                        except:
                            pass
                hybrid_agent.models.clear()
                import gc
                gc.collect()
                logger.info("Modelos descarregados com sucesso")
        except Exception as e:
            logger.error(f"Erro ao limpar modelos: {e}")

    import atexit
    atexit.register(cleanup)

    logger.info("Iniciando configuração do servidor...")

    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Porta configurada: {port}")

    logger.info("Rotas disponíveis:")
    for rule in app.url_map.iter_rules():
        logger.info(f"- {rule.endpoint}: {rule}")

    try:
        print(f"Servidor rodando em: http://127.0.0.1:{port}")
        logger.info(f"Iniciando servidor Flask em http://127.0.0.1:{port}")
        logger.info(f"Modo de depuração: {'Ativado' if app.debug else 'Desativado'}")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        logger.critical(f"Falha crítica ao iniciar servidor: {e}")
        raise

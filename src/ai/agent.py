import os, re, json, time
import logging
from ai.templates import CodeTemplates
from ai.context_manager import ContextManager
from ai.online_search import OnlineSearchManager
from ai.model_setup import load_optimized_model, get_optimal_generation_params

logger = logging.getLogger("hybrid_ide_ai")  # Usar logger específico de IA

class IAAgentHybrid:
    def clear_prompt_cache(self, prompt):
        """Remove o cache de resposta para um prompt específico."""
        cache_key = self._sanitize_input(prompt).strip().lower()
        if cache_key in self.response_cache:
            del self.response_cache[cache_key]
            self._save_cache_to_file()
    def health_check(self):
        """Verifica periodicamente se os modelos estão carregados e operacionais."""
        import time
        status = {
            'chat': self.models.get('chat') is not None,
            'code': self.models.get('code') is not None,
            'last_check': time.time()
        }
        self._save_health_status(status)
        return status

    def _save_health_status(self, status):
        """Salva status de health-check em arquivo para consulta externa."""
        health_path = os.path.join(os.path.dirname(__file__), '../assets/health_status.json')
        try:
            with open(health_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[IAAgentHybrid] Falha ao salvar health-check: {e}")
    def _sanitize_input(self, msg):
        """Sanitiza o prompt do usuário para evitar comandos maliciosos e entradas perigosas."""
        # Remove comandos de sistema, scripts, tags perigosas e normaliza espaços
        msg = re.sub(r'<script.*?>.*?</script>', '', msg, flags=re.IGNORECASE|re.DOTALL)
        msg = re.sub(r'(rm\s+-rf|shutdown|format\s+|os\.system|subprocess|exec|eval|open\(|import\s+os|import\s+sys)', '[REMOVIDO]', msg, flags=re.IGNORECASE)
        msg = re.sub(r'[\x00-\x1F\x7F]', '', msg)  # Remove caracteres de controle
        msg = re.sub(r'\s+', ' ', msg).strip()
        return msg
    """
    IAAgentHybrid gerencia dois modelos locais (chat e código),
    respondendo perguntas e gerando código de forma contextualizada e humanizada.
    """
    def __init__(self, chat_model_path, code_model_path, n_ctx=4096):
        """Inicializa os modelos de chat e código com o contexto especificado."""
        self.models = {}
        self.n_ctx = n_ctx
        self.models['chat'] = self._load_model(chat_model_path, 'chat')
        self.models['code'] = self._load_model(code_model_path, 'code')
        self.last_code = None
        
        # Gerenciador de contexto e busca online
        self.context = ContextManager()
        self.online_search = OnlineSearchManager()
        
        # Cache separado para chat e código
        self.response_cache = {'chat': {}, 'code': {}}
        self.cache_max_size = 50
        self.cache_file = {
            'chat': os.path.join(os.path.dirname(__file__), '../assets/chat_cache.json'),
            'code': os.path.join(os.path.dirname(__file__), '../assets/code_cache.json')
        }
        self._load_cache_from_file()
        
        # Inicializar templates
        self.templates = CodeTemplates()
        
        # Parâmetros otimizados baseados na capacidade real dos modelos
        self.model_params = {
            'chat': {
                'base_temp': 0.7,
                'max_tokens': 3072,    # ~75% do contexto total (4096)
                'min_tokens': 128,     # Garante respostas significativas
                'context_length': 4096 # Limite real do modelo
            },
            'code': {
                'base_temp': 0.7,        # Aumentado para permitir mais criatividade
                'max_tokens': 8192,    # ~50% do contexto máximo (16384)
                'min_tokens': 64,      # Mínimo para código útil
                'context_length': 16384 # Limite real do modelo
            }
        }
        
        # Configurações de busca online
        self.online_search_enabled = True  # Pode ser desativado se necessário
    def _load_cache_from_file(self):
        """Carrega cache de respostas do arquivo JSON, se existir."""
        try:
            for model_type in ['chat', 'code']:
                cache_file = self.cache_file[model_type]
                if os.path.exists(cache_file):
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        self.response_cache[model_type] = json.load(f)
        except Exception as e:
            print(f"[IAAgentHybrid] Falha ao carregar cache: {e}")
            self.response_cache = {'chat': {}, 'code': {}}

    def _save_cache_to_file(self):
        """Salva cache de respostas no arquivo JSON."""
        try:
            # Garante que o diretório assets existe
            assets_dir = os.path.join(os.path.dirname(__file__), '../assets')
            os.makedirs(assets_dir, exist_ok=True)
            
            # Salva cada tipo de cache separadamente
            for model_type in ['chat', 'code']:
                cache_file = self.cache_file[model_type]
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(self.response_cache[model_type], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[IAAgentHybrid] Falha ao salvar cache: {e}")

    def _load_model(self, path, tag):
        """Carrega um modelo gguf com otimizações."""
        try:
            model = load_optimized_model(path, tag)
            if model:
                logger.info(f"Modelo '{tag}' carregado com otimizações de: {path}")
            return model
        except Exception as e:
            logger.error(f"Erro ao carregar modelo '{tag}': {e}")
            return None

    def _get_dynamic_temperature(self, msg):
        """Determina a temperatura ideal baseado no contexto e tipo de pergunta."""
        msg_l = msg.lower()
        base_temp = self.model_params['chat']['base_temp']
        
        # Ajustes baseados no tipo de conteúdo
        if any(w in msg_l for w in ["criativo", "imagine", "crie", "desenhe", "design"]):
            return base_temp + 0.25  # Mais criatividade
        elif any(w in msg_l for w in ["exato", "preciso", "técnico", "específico"]):
            return max(0.1, base_temp - 0.3)  # Mais precisão
        
        # Ajustes baseados no contexto atual
        if self.context.current_context['topic'] == 'programming':
            return base_temp - 0.2  # Mais preciso para programação
        elif self.context.current_context['topic'] == 'explanation':
            return base_temp + 0.1  # Mais variado para explicações
        
        return base_temp

    def _is_valid_response(self, response, query):
        """Verifica se a resposta é técnica e relevante."""
        if not response:
            return False
            
        response_lower = response.lower()
        query_lower = query.lower()
        
        # Padrões que indicam respostas problemáticas
        problematic_patterns = [
            # Respostas evasivas ou vazias
            r"não (sei|entendi|posso)",
            r"desculpe, mas não",
            r"não tenho certeza",
            # Fingindo experiências
            r"quando (eu|nós) (usei|fiz)",
            r"na minha vida",
            r"minha experiência pessoal",
            # Extremamente genérico
            r"^é importante$",
            r"^existem várias$",
            r"^depende$",
            # Robótico demais
            r"^processando sua solicitação$",
            r"^conforme solicitado$",
            r"^executando comando$"
        ]
        
        # Checa padrões problemáticos
        for pattern in problematic_patterns:
            if re.search(pattern, response_lower):
                return False
                
        # Verifica comprimento mínimo contextual
        min_length = 50  # Base
        if '?' in query:
            min_length = 100  # Perguntas precisam mais detalhe
        if any(w in query_lower for w in ['explique', 'detalhe', 'como']):
            min_length = 150  # Explicações precisam ainda mais
            
        if len(response) < min_length:
            return False
            
        # Verifica relevância ao tópico
        query_words = set(re.findall(r'\w+', query_lower))
        response_words = set(re.findall(r'\w+', response_lower))
        relevance = len(query_words & response_words) / len(query_words)
        
        if relevance < 0.3:  # Menos de 30% das palavras da pergunta aparecem na resposta
            return False
            
        return True

    def _should_search_online(self, msg: str) -> bool:
        """Determina se deve realizar busca online baseado na mensagem."""
        msg_lower = msg.lower()
        
        # Palavras-chave que indicam necessidade de informação atual
        search_indicators = [
            'como funciona',
            'o que é',
            'explique',
            'me fale sobre',
            'qual',
            'quando',
            'onde',
            'por que',
            'documentação',
            'exemplo de',
            'tutorial',
            'erro',
            'problema com',
            'versão atual',
            'última versão',
            'api',
            'biblioteca',
            'framework'
        ]
        
        # Verifica indicadores de busca
        if any(indicator in msg_lower for indicator in search_indicators):
            return True
            
        # Evita busca para comandos diretos
        if any(cmd in msg_lower for cmd in ['gere', 'crie', 'faça', 'mostre']):
            return False
            
        # Verifica se é uma pergunta
        if '?' in msg or any(w in msg_lower for w in ['como', 'qual', 'quando', 'onde', 'por que']):
            return True
            
        return False  # Por padrão, não busca

    def _detect_code_type(self, msg):
        """Detecta o tipo de código solicitado na mensagem e contexto."""
        msg_l = msg.lower()
        
        # Primeiro checa o contexto atual
        if self.context.current_context.get('last_code_type'):
            # Se a mensagem parece ser continuação
            if any(w in msg_l for w in ['continue', 'adicione', 'modifique', 'melhore']):
                return self.context.current_context['last_code_type']
        
        # Detecção avançada de Python
        python_patterns = [
            r'python|\.py|script python',  # Menções diretas
            r'input\s*\(|print\s*\(',      # Funções comuns
            r'def\s+\w+|class\s+\w+',     # Definições
            r'while\s+|for\s+in',         # Loops
            r'if\s+.*:|else\s*:',         # Condicionais
            r'import\s+\w+',              # Imports
            r'lista|dicionário|tupla',    # Tipos de dados
            r'variável|função|método',     # Termos em português
            r'calcul|loop|repet',         # Conceitos gerais
            r'tabuada|número|soma'        # Termos matemáticos
        ]
        if any(re.search(pattern, msg_l) for pattern in python_patterns):
            return 'python'
            
        # Outras linguagens
        elif re.search(r'javascript|js|node|\.js', msg_l):
            return 'javascript'
        elif re.search(r'html|página|site|blog|css', msg_l):
            return 'html'
        elif re.search(r'java|\.java|classe|public class', msg_l):
            return 'java'
        elif re.search(r'c\+\+|cpp|\.cpp', msg_l):
            return 'cpp'
        
        # Análise de contexto geral
        elif re.search(r'função|def|return|print', msg_l):
            return 'python'  # Default para funções simples
        elif re.search(r'página|estilo|layout|design', msg_l):
            return 'html'    # Default para conteúdo web
            
        # Usa o contexto de código anterior
        code_context = self.context.get_code_context()
        if code_context:
            if 'def ' in code_context or 'print(' in code_context:
                return 'python'
            elif '<html' in code_context or '<div' in code_context:
                return 'html'
            elif 'function' in code_context or 'const ' in code_context:
                return 'javascript'
        
        return None  # Não foi possível detectar

    def _detect_lang_instr(self, msg):
        """Gera instruções inteligentes para o modelo, equilibrando técnico e natural."""
        msg_l = msg.lower()
        
        # Instruções para respostas naturais e precisas
        core_instructions = [
            "Mantenha um tom conversacional natural.",
            "Seja preciso e direto nas respostas.",
            "Use linguagem clara e acessível.",
            "Evite formalidades ou prefixos desnecessários.",
            "Seja objetivo mas mantenha empatia.",
            "Comunique com entusiasmo genuíno."
        ]
        
        # Adiciona instruções específicas baseadas no contexto
        if self.context.current_context.get('topic') == 'programming':
            core_instructions.extend([
                "Foque em explicações técnicas e código.",
                "Use exemplos específicos e práticos.",
                "Cite fontes técnicas quando relevante."
            ])
        
        # Define idioma de forma natural
        if re.search(r'[ãêõçáéíóúâêôà]|você|exemplo|código|explicação', msg_l):
            lang_instr = 'Comunique em português do Brasil de forma natural e direta.'
        elif re.search(r'[ñáéíóú]|usted|código|ejemplo|explicar', msg_l):
            lang_instr = 'Comunique en español de forma natural y directa.'
        else:
            lang_instr = 'Communicate naturally and directly in English.'
            
        # Monta instrução final
        return f"{lang_instr}\n\n" + "\n".join(core_instructions) + "\n\n"

    def reply_chat(self, msg, force_new=False):
        """Responde a um prompt do usuário, usando contexto e ambos os modelos de forma inteligente."""
        import logging, time
        logger = logging.getLogger("hybrid_ide_api")
        
        # Sanitizar entrada
        clean_msg = self._sanitize_input(msg)
        cache_key = clean_msg.strip().lower()
        
        # Adiciona mensagem ao contexto
        self.context.add_message('user', clean_msg)
        
        # Verificar se é pedido de código
        is_code_request = self._is_code_request(msg)
        
        # Se não for pedido de código e não forçar novo, tenta cache
        if not is_code_request and not force_new and cache_key in self.response_cache['chat']:
            cached = self.response_cache['chat'][cache_key]
            # Verificar TTL do cache (24 horas para chat)
            if time.time() - cached.get('timestamp', 0) < 24 * 3600:
                response = cached['response']
                self.context.add_message('assistant', response[0] if isinstance(response, tuple) else response)
                logger.info(f"[IAAgentHybrid] Usando resposta em cache para chat: '{clean_msg[:50]}...'")
                return response
        
        logger.info(f"[IAAgentHybrid] Gerando nova resposta para: '{clean_msg[:50]}...'")
        
        if not self.models['chat']:
            return "Erro: modelo de chat não disponível.", None
            
        try:
            # Construir prompt com contexto
            context_prompt = self.context.get_context_prompt()
            lang_instr = self._detect_lang_instr(clean_msg)
            
            # Enriquecer com busca online se apropriado
            online_info = ""
            if self.online_search_enabled and self._should_search_online(clean_msg):
                try:
                    enriched_data = self.online_search.enrich_response(
                        clean_msg,
                        self.context.current_context
                    )
                    online_info = self.online_search.format_enriched_data(enriched_data)
                except Exception as e:
                    logger.warning(f"Erro na busca online: {e}")
            
            # Prompt principal com contexto e informações online
            main_prompt = f"{lang_instr}\n\n{context_prompt}\n\n{online_info}\n\nPergunta atual: {clean_msg.strip()}"
            
            # Ajuste dinâmico de temperatura baseado em contexto
            temp = self._get_dynamic_temperature(clean_msg)
            
            # Ajuste inteligente de tokens baseado na capacidade real do modelo
            params = self.model_params['chat']
            context_length = params['context_length']
            max_available = context_length - len(main_prompt)  # Tokens disponíveis após prompt
            
            # Define tokens base considerando o espaço disponível
            base_tokens = min(params['max_tokens'], max_available * 0.75)  # Usa 75% do espaço disponível
            
            # Ajustes por tipo de pergunta (limitados ao disponível)
            if len(context_prompt) > 500:  # Contexto longo
                base_tokens = min(base_tokens * 1.3, max_available * 0.85)
            if len(clean_msg.split()) > 20:  # Perguntas complexas
                base_tokens = min(base_tokens * 1.2, max_available * 0.85)
            if any(w in clean_msg.lower() for w in ['explique', 'detalhe', 'descreva', 'como', 'exemplo']):
                base_tokens = min(base_tokens * 1.15, max_available * 0.85)
                
            # Garante tokens mínimos e máximos seguros
            max_tokens = max(params['min_tokens'], min(int(base_tokens), max_available))
            
            # Configuração otimizada usando limites reais do modelo
            generation_config = {
                'max_tokens': max_tokens,
                'temperature': temp,
                'top_p': 0.9,
                'repeat_penalty': 1.1,  # Reduzido para permitir alguma repetição necessária
                'presence_penalty': 0.05  # Suavizado para manter coerência
            }
            
            # Obter parâmetros otimizados para geração
            gen_params = get_optimal_generation_params('chat', len(clean_msg))
            gen_params.update(generation_config)  # Mantém configurações específicas do contexto
            
            # Gerar resposta com contexto e parâmetros otimizados
            out = self.models['chat'](main_prompt, **gen_params)
            chat_resp = out['choices'][0]['text'].strip()
            
            # Processamento inteligente da resposta
            if len(chat_resp) > 50:  # Aumentado threshold
                chat_resp = self._clean_duplicate_response(chat_resp, msg)
            
            # Análise da qualidade da resposta
            if not self._is_valid_response(chat_resp, clean_msg):
                logger.warning(f"[IAAgentHybrid] Resposta pode não ser adequada, tentando regenerar...")
                # Tenta uma vez com temperatura diferente
                out = self.models['chat'](main_prompt, max_tokens=max_tokens, temperature=temp + 0.2)
                chat_resp = out['choices'][0]['text'].strip()
            
            if not chat_resp:
                logger.warning(f"[IAAgentHybrid] Resposta do modelo de chat veio vazia para: '{msg}'")
            elif not self._is_code_request(msg):  # Só adiciona ao contexto se não for pedido de código
                self.context.add_message('assistant', chat_resp)
                
        except Exception as e:
            logger.error(f"[IAAgentHybrid] Erro no modelo de chat: {e}")
            chat_resp = ''

        code_prompt = None
        code_result = None
        
        # Se for pedido de código, usa o chat para estruturar o pedido
        if self._is_code_request(msg):
            logger.info(f"[IAAgentHybrid] Pedido de código DETECTADO para: '{msg}'")
            
            # Detecta o tipo de código solicitado
            code_type = self._detect_code_type(msg)
            if not code_type:
                code_type = 'html'  # Fallback, mas vamos logar
                logger.warning(f"[IAAgentHybrid] Tipo de código não detectado, usando HTML como fallback para: '{msg}'")
            
            logger.info(f"[IAAgentHybrid] Tipo de código detectado: {code_type}")
            
            # Primeiro usa o chat para estruturar o pedido de código
            code_prep_prompt = f"""Estruture um pedido preciso de código para: {msg}
Considere:
1. Deve ser código em {code_type}
2. Inclua todos os detalhes técnicos necessários
3. Seja específico sobre a funcionalidade desejada
4. Mantenha apenas informações relevantes para o código

Responda apenas com o pedido estruturado, sem explicações adicionais."""

            code_prep_params = {
                'max_tokens': 256,
                'temperature': 0.1,
                'top_p': 0.1,
                'repeat_penalty': 1.1
            }
            
            try:
                prep_out = self.models['chat'](code_prep_prompt, **code_prep_params)
                structured_prompt = prep_out['choices'][0]['text'].strip()
                logger.info(f"[IAAgentHybrid] Prompt estruturado: {structured_prompt}")
            except Exception as e:
                logger.error(f"[IAAgentHybrid] Erro ao estruturar prompt: {e}")
                structured_prompt = msg
            
            # Agora usa o prompt estruturado para gerar o código
            code_context = self.context.get_code_context() or ""
            
            # Gera prompt específico para o tipo de código
            code_prompts = {
                'python': f"""Escreva apenas o código Python para: {msg.strip()}

O código deve:
- Ser funcional e pronto para executar
- Incluir tratamento de erros básico
- Ter comentários explicativos
- Seguir PEP 8
- Não ter cabeçalhos ou docstrings desnecessários

{code_context if code_context else ''}""",
                'javascript': f"Gere exclusivamente código JavaScript funcional e completo para:\n{msg.strip()}\n{code_context}",
                'html': f"Gere exclusivamente código HTML/CSS funcional e completo para:\n{msg.strip()}\n{code_context}",
                'java': f"Gere exclusivamente código Java funcional e completo para:\n{msg.strip()}\n{code_context}",
                'cpp': f"Gere exclusivamente código C++ funcional e completo para:\n{msg.strip()}\n{code_context}"
            }
            
            code_prompt = code_prompts.get(code_type, code_prompts['html'])
            
            # Gera código com contexto do tipo
            code_result = self._generate_code(code_prompt, code_type)
            
            if code_result:
                self.last_code = code_result
                # Resposta mínima do chat, já que o foco é o código
                chat_resp = f"Gerando código em {code_type}..."
            else:
                logger.warning(f"[IAAgentHybrid] Modelo de código não conseguiu gerar código útil")
                chat_resp = "Desculpe, não consegui gerar o código solicitado. Pode reformular o pedido?"
        else:
            self.last_code = None

        # Feedback amigável em caso de erro
        if not chat_resp and not self.last_code:
            chat_resp = "Pode detalhar um pouco mais o que você precisa?"
        
        # CACHE DESATIVADO TEMPORARIAMENTE
        result = (chat_resp, self.last_code if is_code_request else None, code_type if is_code_request else None)
        return result

    def _is_code_request(self, prompt):
        """Detecta qualquer pedido de geração de código, HTML, CSS, frontend, etc. Muito tolerante."""
        terms = [
            # Português e inglês
            r"html", r"css", r"div", r"body", r"head", r"form", r"input", r"campo", r"tabela", r"table", r"style", r"layout", r"visual", r"página", r"pagina", r"exiba", r"exibir", r"mostre", r"mostrar", r"botão", r"botao", r"button",
            r"crie", r"faça", r"faça um", r"faça uma", r"faça o", r"faça a", r"código", r"código para", r"exemplo de código", r"script", r"programa", r"implemente", r"front", r"frontend", r"python", r"javascript", r"js", r"json", r"salvar como", r"template", r"arquivo ",
            r"escreva", r"gere", r"demonstre", r"complete o código", r"monte um", r"criar um código", r"criar um html", r"desenvolva", r"interface", r"interface web", r"em html", r"em js", r"em css",
            # Inglês (para pegar de tudo)
            r"code", r"generate an html", r"create an html", r"show code", r"display code", r"create a form", r"make an html", r"generate code", r"script in python", r"script in js", r"script in html",
        ]
        texto = prompt.lower()
        for term in terms:
            if re.search(term, texto):
                return True
        return False

    def _extract_code_prompt(self, chat_resp, prompt):
        """Extrai contexto do usuário para geração mais precisa de código."""
        # Extrair contexto mais específico para geração de código
        code_context_terms = [
            r"crie um html", r"gere um site", r"desenvolva uma pagina",
            r"template html", r"interface web"
        ]
        for term in code_context_terms:
            match = re.search(term, prompt.lower())
            if match:
                return prompt[match.start():].strip()
        return prompt.strip()

    def _generate_code(self, code_prompt, lang_type=None):
        """Gera código a partir do prompt usando o modelo code com estratégias avançadas e validações rígidas."""
        import logging
        logger = logging.getLogger("hybrid_ide_ai")
        
        if not self.models['code']:
            logger.error("[IAAgentHybrid] Modelo de código não disponível")
            return None
            
        try:
            # Log de debug para rastrear detalhes da geração
            logger.debug(f"Gerando código para linguagem: {lang_type}")
            logger.debug(f"Prompt de geração: {code_prompt[:500]}...")  # Limita log para não sobrecarregar
            
            # Exemplos de código mais contextuais e abrangentes
            language_examples = {
                'python': {
                    'basic': 'def calcular_media(numeros):\n    return sum(numeros) / len(numeros) if numeros else 0',
                    'advanced': 'class GerenciadorTarefas:\n    def __init__(self):\n        self.tarefas = []\n    \n    def adicionar_tarefa(self, tarefa):\n        self.tarefas.append({"descricao": tarefa, "concluida": False})\n    \n    def listar_tarefas(self):\n        return [t["descricao"] for t in self.tarefas]\n',
                    'error_handling': 'def dividir(a, b):\n    try:\n        return a / b\n    except ZeroDivisionError:\n        return "Erro: Divisão por zero não permitida"\n'
                },
                'javascript': {
                    'basic': 'function gerarNumeroAleatorio(min, max) {\n    return Math.floor(Math.random() * (max - min + 1)) + min;\n}',
                    'advanced': 'class GerenciadorEstado {\n    constructor() {\n        this.estado = {};\n    }\n\n    definirEstado(chave, valor) {\n        this.estado[chave] = valor;\n    }\n\n    obterEstado(chave) {\n        return this.estado[chave];\n    }\n}',
                    'async': 'async function buscarDadosAPI(url) {\n    try {\n        const resposta = await fetch(url);\n        return await resposta.json();\n    } catch (erro) {\n        console.error("Erro na busca:", erro);\n        return null;\n    }\n'
                },
                'html': {
                    'basic': '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n    <meta charset="UTF-8">\n    <title>Página Simples</title>\n</head>\n<body>\n    <h1>Olá, Mundo!</h1>\n</body>\n</html>',
                    'form': '<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n    <meta charset="UTF-8">\n    <title>Formulário de Contato</title>\n    <style>\n        body { font-family: Arial, sans-serif; max-width: 400px; margin: 0 auto; }\n        input, textarea { width: 100%; margin: 10px 0; }\n    </style>\n</head>\n<body>\n    <form>\n        <input type="text" placeholder="Nome" required>\n        <input type="email" placeholder="E-mail" required>\n        <textarea placeholder="Sua mensagem" required></textarea>\n        <button type="submit">Enviar</button>\n    </form>\n</body>\n</html>'
                }
            }
            
            # Seleção dinâmica de exemplo baseado no contexto
            example_type = 'advanced' if len(code_prompt) > 100 else 'basic'
            example = language_examples.get(lang_type, {}).get(example_type, '')
            
            # Prompt de geração refinado
            pure_code_prompt = f"""Gere código {lang_type or 'html'} seguindo RIGOROSAMENTE estas diretrizes:

Contexto da Tarefa:
{code_prompt}

REGRAS ABSOLUTAS:
1. Código 100% funcional e executável
2. Sem comentários desnecessários
3. Foco em clareza e eficiência
4. Tratar casos de erro básicos
5. Usar boas práticas da linguagem

Gere APENAS o código, sem explicações, markdown ou prefixos."""
            
            # Parâmetros de geração otimizados
            code_stops = {
                'python': ['\ndef ', '```', '###', '\n# ', '\nclass '],
                'html': ['</html>', '```', '<!----', '<!--', '</body>'],
                'javascript': ['\nfunction ', '```', '//', '/*', '\nconst ', '\nlet '],
                'java': ['\npublic ', '```', '//'],
                'cpp': ['\n#include ', '```', '//']
            }
            
            stops = code_stops.get(lang_type or 'html', ['```'])
            gen_params = get_optimal_generation_params('code', len(pure_code_prompt))
            gen_params['max_tokens'] = 1024
            gen_params['stop'] = stops
            gen_params['temperature'] = 0.2
            gen_params['top_p'] = 0.9
            
            # Geração de código
            try:
                code_out = self.models['code'](pure_code_prompt, **gen_params)
                result = code_out['choices'][0]['text'].strip()
                
                logger.debug(f"Código gerado bruto (primeiros 200 chars): {result[:200]}...")
            except Exception as code_gen_error:
                logger.error(f"Erro crítico na geração de código: {code_gen_error}")
                return None
            
            # Validações rígidas contra código inválido
            def is_valid_code(code, lang_type):
                # Verifica se o código não é apenas repetições ou lixo
                if not code or len(code) < 20:
                    logger.warning(f"Código muito curto para {lang_type}")
                    return False
                
                # Verifica repetições excessivas
                if len(set(code.split('\n'))) < 3:
                    logger.warning(f"Código repetitivo para {lang_type}")
                    return False
                
                # Verificações específicas por linguagem
                checks_by_language = {
                    'python': [
                        re.search(r'def\s+\w+\(', code) or 
                        re.search(r'class\s+\w+:', code) or 
                        re.search(r'import\s+\w+', code)
                    ],
                    'html': [
                        re.search(r'<!DOCTYPE\s+html>', code, re.I),
                        re.search(r'<html', code),
                        re.search(r'<body', code)
                    ],
                    'javascript': [
                        re.search(r'function\s+\w+\(', code) or 
                        re.search(r'const\s+\w+\s*=', code) or 
                        re.search(r'let\s+\w+\s*=', code)
                    ]
                }
                
                language_checks = checks_by_language.get(lang_type, [])
                
                if not all(language_checks):
                    logger.warning(f"Código não passou nas verificações para {lang_type}")
                    return False
                
                return True
            
            # Verifica validade do código
            if not is_valid_code(result, lang_type):
                logger.warning(f"Código gerado inválido para {lang_type}")
                return None
            
            logger.debug(f"Código gerado com sucesso para {lang_type}")
            return result.strip()
                
        except Exception as e:
            logger.error(f"[IAAgentHybrid] Erro inesperado na geração de código: {e}")
            return None

    def _clean_duplicate_response(self, text, original_msg=None):
        """Limpa respostas duplicadas ou repetitivas da IA para maior naturalidade."""
        # Limpeza simples e eficaz
        lines = text.split('\n')
        cleaned_lines = []
        seen = set()
        
        for line in lines:
            line = line.strip()
            if line and line not in seen and len(line) > 5:
                # Evita repetições e loops
                if not re.search(r'^(E aí|Você tem|Você está).*', line):
                    cleaned_lines.append(line)
                    seen.add(line)
        
        # Limita a 3 linhas para evitar loops
        result = '\n'.join(cleaned_lines[:3])
        
        # Se resposta muito estranha, limpa mais
        if len(result) < 10 or re.search(r'[E aí|Você tem|Você está].*[E aí|Você tem|Você está]', result):
            # Remove linhas problemáticas e pega só as primeiras
            clean_lines = [line for line in lines[:2] if line.strip() and len(line.strip()) > 5]
            result = '\n'.join(clean_lines) if clean_lines else result
        
        return result

    def _add_to_cache(self, key, value):
        """Adiciona resposta ao cache com timestamp, respeitando limite de tamanho e persistindo em arquivo."""
        # Não armazena código em cache - apenas respostas de chat
        if self._is_code_request(key):
            return
            
        current_time = time.time()
        expired_keys = []
        
        # Remove entradas de chat expiradas (24 horas)
        for k, v in self.response_cache.items():
            if current_time - v.get('timestamp', 0) > 24 * 3600:
                expired_keys.append(k)
                
        for k in expired_keys:
            del self.response_cache[k]
            
        # Se cache estiver cheio, remove o mais antigo
        if len(self.response_cache) >= self.cache_max_size:
            oldest_key = min(self.response_cache.keys(), 
                           key=lambda k: self.response_cache[k].get('timestamp', 0))
            del self.response_cache[oldest_key]
            
        # Adiciona apenas respostas de chat no cache
        self.response_cache[key] = {
            'response': value,
            'timestamp': current_time
        }
        
        self._save_cache_to_file()

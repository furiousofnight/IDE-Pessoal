import os
from ai.agent import IAAgentHybrid
from chat.history import ChatHistory
from settings.user_settings import UserSettings

# Caminhos para os modelos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LLAMA2_CHAT_PATH = os.path.join(BASE_DIR, '../model/llama-2-7b-chat.Q4_K_M.gguf')
STABLE_CODE_PATH = os.path.join(BASE_DIR, '../model/stable-code-3b.Q8_0.gguf')

def main():
    # Inicialização dos componentes principais
    hybrid_agent = IAAgentHybrid(LLAMA2_CHAT_PATH, STABLE_CODE_PATH)
    history = ChatHistory()
    settings = UserSettings()
    
    print("\n--- Status do Sistema ---")
    chat_ready = (hybrid_agent.models.get('chat', None) is not None)
    code_ready = (hybrid_agent.models.get('code', None) is not None)
    print(f"Modelo de Chat: {'Pronto' if chat_ready else 'Não inicializado'}")
    print(f"Modelo de Código: {'Pronto' if code_ready else 'Não inicializado'}")
    
    print("\n--- Teste do Agente Híbrido ---")
    resp, code = hybrid_agent.reply_chat("Olá, você está funcionando?")
    print(f"Resposta do Chat: {resp}")
    if code:
        print(f"Código Gerado: {code}")
    
    print("\n--- Histórico e Configurações ---")
    history.add_message("Olá!", "user")
    print(f"Último histórico: {history.get_history()[-1] if history.get_history() else 'Nenhum'}")
    print(f"Configurações atuais: {settings.get_settings()}")
    
    print("\n--- Instruções de Uso ---")
    print("1. Execute 'python src/serve_main.py' para iniciar o servidor")
    print("2. Abra http://localhost:5000 no navegador")
    print("3. Interface completa com:")
    print("   - Chat com IA e geração de código")
    print("   - Preview de código em tempo real")
    print("   - Gerenciamento de arquivos")
    print("   - Configurações personalizáveis")

if __name__ == "__main__":
    main()

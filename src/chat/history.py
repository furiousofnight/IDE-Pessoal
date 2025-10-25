import os
import json

class ChatHistory:
    def __init__(self, path="logs/chat_history.json"):
        self.path = path
        self.conversations = []
        self.load()
    def add_message(self, msg, role="user", metadata=None):
        """
        Adiciona mensagem ao histórico com validação e otimização.
        
        Args:
            msg: Conteúdo da mensagem
            role: Papel do emissor ('user', 'assistant', 'system', 'code')
            metadata: Metadados opcionais (tempo de resposta, tokens, etc)
        """
        import datetime
        
        # Validação de entrada
        if not isinstance(msg, str) or not msg.strip():
            return False
            
        if role not in ['user', 'assistant', 'system', 'code']:
            role = 'user'  # Fallback seguro
            
        # Limpeza e normalização
        msg = msg.strip()
        
        entry = {
            "id": len(self.conversations) + 1,
            "timestamp": datetime.datetime.now().isoformat(),
            "role": role,
            "content": msg,
            "metadata": metadata or {},
            "session_id": self._get_session_id()
        }
        
        self.conversations.append(entry)
        
        # Gerenciamento de memória
        max_msgs = 1000  # Aumentado mas com limpeza seletiva
        if len(self.conversations) > max_msgs:
            # Mantém mensagens mais recentes e importantes
            self._optimize_history(max_msgs)
            
        # Salva automaticamente a cada X mensagens
        if len(self.conversations) % 10 == 0:
            self.save()
            
    def _get_session_id(self):
        """Gera ou retorna ID da sessão atual"""
        if not hasattr(self, '_current_session_id'):
            import uuid
            self._current_session_id = str(uuid.uuid4())
        return self._current_session_id
        
    def _optimize_history(self, max_size):
        """Otimiza o histórico mantendo mensagens importantes"""
        if len(self.conversations) <= max_size:
            return
            
        # Prioriza mensagens por importância
        important = [msg for msg in self.conversations 
                    if msg.get('metadata', {}).get('important', False) 
                    or msg['role'] in ['system', 'code']]
                    
        # Calcula quantas mensagens regulares podemos manter
        regular_limit = max_size - len(important)
        if regular_limit < 0:
            regular_limit = max_size // 2
            
        # Pega as mensagens mais recentes que não são importantes
        regular = [msg for msg in self.conversations 
                  if msg not in important][-regular_limit:]
                  
        # Combina e ordena por timestamp
        self.conversations = sorted(
            important + regular,
            key=lambda x: x['timestamp']
        )
        if len(self.conversations) % 10 == 0:
            self.save()
        
        self.save()
    def clear(self):
        """Limpa todo o histórico manualmente."""
        self.conversations = []
        self.save()
    def get_history(self):
        return self.conversations
    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=2)
    def load(self):
        if os.path.exists(self.path):
            with open(self.path, 'r', encoding='utf-8') as f:
                self.conversations = json.load(f)

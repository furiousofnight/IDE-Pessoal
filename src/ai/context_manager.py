"""
Gerenciador de contexto avançado para o sistema híbrido de IA.
Mantém e analisa histórico de conversas, contexto de código e preferências
para melhorar a qualidade das respostas dos modelos.
"""
import json
import os
from typing import List, Dict, Optional, Union
import re
from datetime import datetime

class ContextManager:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.conversation_history: List[Dict] = []
        self.current_context: Dict = {
            'topic': None,
            'code_context': None,
            'user_preferences': {},
            'last_code_type': None,
            'last_code_language': None,
            'project_context': None,
            'session_start': datetime.now().isoformat(),
            'model_performance': {
                'chat': {'success_rate': 1.0, 'total_calls': 0},
                'code': {'success_rate': 1.0, 'total_calls': 0}
            }
        }
        self.context_file = os.path.join(os.path.dirname(__file__), '../assets/context.json')
        self._load_saved_context()
    
    def _load_saved_context(self):
        """Carrega contexto salvo se existir."""
        try:
            if os.path.exists(self.context_file):
                try:
                    with open(self.context_file, 'r', encoding='utf-8') as f:
                        saved = json.load(f)
                except (json.JSONDecodeError, UnicodeError):
                    # Se o arquivo principal estiver corrompido, tenta o backup
                    backup_file = f"{self.context_file}.bak"
                    if os.path.exists(backup_file):
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            saved = json.load(f)
                    else:
                        saved = {}
                
                # Atualiza apenas preferências e contexto de projeto
                self.current_context['user_preferences'] = saved.get('user_preferences', {})
                self.current_context['project_context'] = saved.get('project_context', None)
                
        except Exception as e:
            print(f"[ContextManager] Erro ao carregar contexto: {e}")
            # Garante valores padrão em caso de erro
            self.current_context['user_preferences'] = {}
            self.current_context['project_context'] = None
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """
        Adiciona mensagem ao histórico com análise de contexto e metadados.
        
        Args:
            role: Papel da mensagem ('user', 'assistant', 'system', 'code')
            content: Conteúdo da mensagem
            metadata: Metadados opcionais (tempo de resposta, tokens, etc)
        """
        message = {
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self.conversation_history.append(message)
        
        # Mantém apenas as últimas N mensagens
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)
        
        # Atualiza contexto e salva
        self._update_context(content, role, metadata)
        self._save_context()
    
    def _update_context(self, content: str, role: str, metadata: Dict = None):
        """Analisa mensagem para atualizar contexto atual com análise avançada."""
        content_lower = content.lower()
        
        # Atualiza métricas de performance dos modelos
        if metadata and 'model_type' in metadata:
            model_type = metadata['model_type']  # 'chat' ou 'code'
            success = metadata.get('success', True)
            stats = self.current_context['model_performance'][model_type]
            stats['total_calls'] += 1
            # Atualiza taxa de sucesso com peso móvel
            if stats['total_calls'] > 1:
                stats['success_rate'] = (stats['success_rate'] * 0.8) + (1.0 if success else 0.0) * 0.2
            else:
                stats['success_rate'] = 1.0 if success else 0.0
        
        # Detecta tópico e contexto técnico
        if role == 'user':
            # Análise de tópico mais granular
            if re.search(r'código|programa|desenvolv|implement|bug|error|debug', content_lower):
                self.current_context['topic'] = 'programming'
            elif re.search(r'explique|como|qual|por que|defin|conceito', content_lower):
                self.current_context['topic'] = 'explanation'
            elif re.search(r'ajuda|erro|problema|não consigo|falha', content_lower):
                self.current_context['topic'] = 'help'
            elif re.search(r'teste|validar|verificar|assert|spec', content_lower):
                self.current_context['topic'] = 'testing'
            
            # Detecta linguagem de programação
            langs = ['python', 'javascript', 'java', 'c#', 'cpp', 'ruby', 'go', 'rust']
            for lang in langs:
                if lang in content_lower:
                    self.current_context['last_code_language'] = lang
                    break
    
    def get_context_prompt(self, model_type: str = 'chat') -> str:
        """
        Gera prompt com contexto otimizado para o tipo de modelo.
        
        Args:
            model_type: 'chat' ou 'code' para otimizar o contexto
        """
        prompt_parts = []
        
        # Contexto base com metadados
        if model_type == 'chat':
            prompt_parts.append(f"Sessão iniciada em: {self.current_context['session_start']}")
            if self.current_context['topic']:
                prompt_parts.append(f"Tópico atual: {self.current_context['topic']}")
        
        # Histórico recente relevante
        if self.conversation_history:
            relevant_history = self._get_relevant_history(model_type)
            if relevant_history:
                prompt_parts.append("\nHistórico relevante:")
                prompt_parts.extend(relevant_history)
        
        # Contexto técnico para código
        if model_type == 'code':
            code_context = self._get_technical_context()
            if code_context:
                prompt_parts.append("\nContexto técnico:")
                prompt_parts.extend(code_context)
        
        # Adiciona preferências do usuário relevantes
        user_prefs = self._get_relevant_preferences(model_type)
        if user_prefs:
            prompt_parts.append("\nPreferências:")
            prompt_parts.extend(user_prefs)
        
        return "\n".join(prompt_parts).strip()
    
    def _get_relevant_history(self, model_type: str) -> List[str]:
        """Filtra e formata histórico relevante baseado no tipo de modelo."""
        history = []
        window = 5 if model_type == 'chat' else 3  # Janela maior para chat
        
        for msg in self.conversation_history[-window:]:
            # Pula mensagens não relevantes para código
            if model_type == 'code' and msg['role'] == 'assistant' and not any(
                marker in msg['content'] for marker in ['```', 'código', 'function', 'class']
            ):
                continue
            
            content = msg['content']
            # Limita tamanho para manter contexto conciso
            if len(content) > 500:
                content = content[:497] + "..."
            
            history.append(f"{msg['role']}: {content}")
        
        return history
    
    def _get_technical_context(self) -> List[str]:
        """Coleta contexto técnico para geração de código."""
        context = []
        
        # Linguagem preferida
        if self.current_context['last_code_language']:
            context.append(f"Linguagem: {self.current_context['last_code_language']}")
        
        # Adiciona fragmentos de código relevantes
        code_fragments = []
        for msg in reversed(self.conversation_history):
            if msg['role'] == 'assistant' and '```' in msg['content']:
                # Extrai apenas o código entre backticks
                code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', msg['content'], re.DOTALL)
                if code_blocks:
                    code_fragments.append(code_blocks[0].strip())
                    if len(code_fragments) >= 2:  # Limita a 2 fragmentos
                        break
        
        if code_fragments:
            context.append("Código relevante anterior:")
            context.extend(code_fragments)
        
        return context
    
    def _get_relevant_preferences(self, model_type: str) -> List[str]:
        """Filtra preferências relevantes para o tipo de modelo."""
        prefs = []
        user_prefs = self.current_context['user_preferences']
        
        if model_type == 'code':
            code_style = user_prefs.get('code_style', {})
            if code_style:
                prefs.extend([
                    f"- Estilo: {code_style.get('style', 'default')}",
                    f"- Indentação: {code_style.get('indent', '4 espaços')}",
                    f"- Documentação: {code_style.get('doc_style', 'detalhada')}"
                ])
        else:
            chat_prefs = user_prefs.get('chat_preferences', {})
            if chat_prefs:
                prefs.extend([
                    f"- Formato: {chat_prefs.get('format', 'conciso')}",
                    f"- Nível técnico: {chat_prefs.get('technical_level', 'médio')}"
                ])
        
        return prefs
    
    def _save_context(self):
        """Salva contexto atual em arquivo."""
        try:
            # Garante que o diretório assets existe
            assets_dir = os.path.dirname(self.context_file)
            os.makedirs(assets_dir, exist_ok=True)
            
            # Salva apenas dados persistentes
            to_save = {
                'user_preferences': self.current_context['user_preferences'],
                'project_context': self.current_context['project_context'],
                'last_save': datetime.now().isoformat()
            }
            
            # Salva usando arquivo temporário para evitar corrupção
            temp_file = f"{self.context_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
            
            # Renomeia para arquivo final (mais seguro em caso de crash)
            if os.path.exists(self.context_file):
                os.replace(self.context_file, f"{self.context_file}.bak")
            os.rename(temp_file, self.context_file)
            
        except Exception as e:
            print(f"[ContextManager] Erro ao salvar contexto: {e}")
    
    def update_preferences(self, preferences: Dict):
        """Atualiza preferências do usuário."""
        self.current_context['user_preferences'].update(preferences)
        self._save_context()
    
    def set_project_context(self, context: Dict):
        """Define contexto do projeto atual."""
        self.current_context['project_context'] = context
        self._save_context()
    
    def get_model_performance(self) -> Dict:
        """Retorna métricas de performance dos modelos."""
        return self.current_context['model_performance']
    
    def get_code_context(self) -> Optional[str]:
        """
        Retorna contexto específico para geração de código.
        Usado pelo agente híbrido para contextualizar geração de código.
        """
        context_parts = []
        
        # Adiciona linguagem se disponível
        if self.current_context['last_code_language']:
            context_parts.append(f"Linguagem: {self.current_context['last_code_language']}")
        
        # Analisa histórico por discussões relevantes de código
        code_blocks = []
        requirements = []
        
        for msg in reversed(self.conversation_history[-10:]):  # Aumentado de 5 para 10 mensagens
            if msg['role'] == 'assistant' and '```' in msg['content']:
                # Extrai código entre backticks
                code = re.findall(r'```(?:\w+)?\n(.*?)```', msg['content'], re.DOTALL)
                if code:
                    code_blocks.append(f"Código anterior gerado:\n{code[0].strip()}")
                    if len(code_blocks) >= 5:  # Aumentado de 2 para 5 blocos de código
                        break
            elif msg['role'] == 'user':
                # Procura por requisitos de código
                content_lower = msg['content'].lower()
                if any(word in content_lower for word in ['código', 'programa', 'função', 'class', 'implementa', 'crie', 'desenvolva', 'faça']):
                    requirements.append(f"Requisito anterior: {msg['content']}")
                    if len(requirements) >= 5:  # Aumentado de 2 para 5 requisitos
                        break
        
        # Adiciona requisitos primeiro
        if requirements:
            context_parts.extend(requirements)
        
        # Depois adiciona código
        if code_blocks:
            context_parts.extend(code_blocks)
        
        # Adiciona preferências de código se existirem
        code_prefs = self.current_context['user_preferences'].get('code_style', {})
        if code_prefs:
            prefs = [
                "Preferências de código:",
                f"- Estilo: {code_prefs.get('style', 'default')}",
                f"- Indentação: {code_prefs.get('indent', '4 espaços')}",
                f"- Documentação: {code_prefs.get('doc_style', 'detalhada')}"
            ]
            context_parts.extend(prefs)
        
        return "\n".join(context_parts) if context_parts else None
    
    def clear(self, save_preferences: bool = True):
        """
        Limpa histórico e contexto.
        
        Args:
            save_preferences: Se True, mantém preferências do usuário
        """
        old_prefs = self.current_context['user_preferences'].copy() if save_preferences else {}
        old_project = self.current_context['project_context']
        
        self.conversation_history.clear()
        self.current_context = {
            'topic': None,
            'code_context': None,
            'user_preferences': old_prefs,
            'last_code_type': None,
            'last_code_language': None,
            'project_context': old_project,
            'session_start': datetime.now().isoformat(),
            'model_performance': {
                'chat': {'success_rate': 1.0, 'total_calls': 0},
                'code': {'success_rate': 1.0, 'total_calls': 0}
            }
        }
"""
Sistema de Templates para Geração de Código
Gerencia a detecção, análise e processamento de código.
"""

import re
import json
import os
from typing import Dict, Optional, List, Any
from datetime import datetime
from pathlib import Path

class CodeTemplates:
    """Gerenciador de templates e processamento de código."""
    
    def __init__(self):
        """Inicializa o gerenciador de templates."""
        self.cache_file = Path(os.path.dirname(__file__)) / '../assets/template_cache.json'
        self.template_cache = self._load_cache()
        self.context = {}
    
    def detect_code_type(self, prompt: str) -> str:
        """
        Detecta o tipo de código solicitado no prompt.
        
        Args:
            prompt: Texto do pedido do usuário
            
        Returns:
            Tipo de código detectado (html, python, javascript, etc)
        """
        prompt = prompt.lower()
        
        # Detecção por palavras-chave específicas e mais abrangente
        code_type_mapping = {
            'html': ['html', 'página', 'site', 'web', 'frontend', 'interface', 'layout', 'design', 'estilo', 'css'],
            'python': ['python', 'script', 'classe', 'função', 'algoritmo', 'dados', 'análise', 'processamento', 'machine learning', 'data science'],
            'javascript': ['javascript', 'js', 'função', 'frontend', 'react', 'vue', 'angular', 'node', 'browser', 'web app'],
            'java': ['java', 'android', 'spring', 'enterprise', 'backend', 'classe', 'objeto'],
            'cpp': ['c++', 'cpp', 'sistema', 'performance', 'baixo nível', 'hardware', 'game'],
            'rust': ['rust', 'sistema', 'segurança', 'performance', 'concorrência'],
            'go': ['go', 'golang', 'concorrência', 'backend', 'microserviços']
        }
        
        # Verifica cada tipo de código
        for lang, keywords in code_type_mapping.items():
            if any(kw in prompt for kw in keywords):
                return lang
        
        # Detecção por contexto e padrões
        context_patterns = {
            'python': [r'def\s+\w+', r'class\s+\w+', r'import\s+\w+'],
            'javascript': [r'function\s+\w+', r'const\s+\w+', r'let\s+\w+'],
            'html': [r'<\w+>', r'<!DOCTYPE\s+html>', r'<head>', r'<body>']
        }
        
        for lang, patterns in context_patterns.items():
            if any(re.search(pattern, prompt, re.I) for pattern in patterns):
                return lang
        
        # Detecção por contexto de exibição ou manipulação
        if any(kw in prompt for kw in ['exibir', 'mostrar', 'interface']):
            return 'html'
        
        return 'text'  # Tipo padrão
    
    def extract_info(self, prompt: str) -> Dict[str, Any]:
        """
        Extrai informações relevantes do prompt do usuário.
        
        Args:
            prompt: Texto do pedido do usuário
            
        Returns:
            Dicionário com informações extraídas e contexto
        """
        info = {
            'content': '',
            'description': '',
            'type': self.detect_code_type(prompt)
        }
        
        # Extração de conteúdo principal com padrões mais abrangentes
        content_patterns = [
            (r'["\']([^"\']+)["\']', 1),  # Texto entre aspas
            (r'(?:exib|mostr)[ae]\s+(?:a\s+)?(?:mensagem|frase?|texto)\s+([^\.!?]+)', 1),
            (r'onde\s+(?:exib|mostr)[ae]\s+([^\.!?]+)', 1),
            (r'que\s+(?:dig|mostr|exib)[ae]\s+([^\.!?]+)', 1),
            (r'criar\s+(?:um\s+)?(?:código|programa|script)\s+(?:que\s+)?([^\.!?]+)', 1),
            (r'desenvolva\s+(?:um\s+)?(?:código|programa|script)\s+(?:que\s+)?([^\.!?]+)', 1)
        ]
        
        for pattern, group in content_patterns:
            if match := re.search(pattern, prompt, re.I):
                info['content'] = match.group(group).strip()
                break
                
        # Extrai descrição se não houver conteúdo
        if not info['content']:
            words = prompt.split()[:12]  # Aumentado de 8 para 12 palavras
            info['content'] = ' '.join(words)
            
        # Adiciona data atual
        info['date'] = datetime.now().strftime('%Y-%m-%d')
        
        return info

    def _load_cache(self) -> Dict:
        """Carrega cache de templates."""
        if self.cache_file.exists():
            try:
                return json.loads(self.cache_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                return {}
        return {}
        
    def _save_cache(self):
        """Salva cache de templates."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(
            json.dumps(self.template_cache, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def set_context(self, **kwargs):
        """
        Define o contexto para geração de código.
        
        Args:
            **kwargs: Dados de contexto (arquivos, dependências, etc)
        """
        self.context.update(kwargs)
        
    def analyze_dependencies(self, code: str, code_type: str) -> List[str]:
        """
        Analisa dependências do código.
        
        Args:
            code: Código para análise
            code_type: Tipo do código
            
        Returns:
            Lista de dependências encontradas
        """
        deps = []
        
        if code_type == 'python':
            # Detecta imports Python
            imports = re.findall(r'^\s*(?:from\s+(\S+)\s+)?import\s+(\S+)', code, re.M)
            deps.extend(m[0] or m[1] for m in imports if m[0] or m[1])
            
        elif code_type == 'html':
            # Detecta dependências web (CSS, JS)
            deps.extend(re.findall(r'href=[\'"](.*?)[\'"]', code))
            deps.extend(re.findall(r'src=[\'"](.*?)[\'"]', code))
            
        return [d for d in deps if not d.startswith(('.', '/'))]

    def format_output(self, code: str, code_type: str, format_type: str = 'default') -> str:
        """
        Formata o código de acordo com o tipo de saída desejado.
        
        Args:
            code: Código para formatar
            code_type: Tipo do código
            format_type: Tipo de formatação ('default', 'minified', 'commented')
            
        Returns:
            Código formatado
        """
        if format_type == 'minified':
            # Remove comentários e espaços extras
            code = re.sub(r'//.*?\n|/\*.*?\*/', '', code, flags=re.S)
            code = re.sub(r'\s+', ' ', code)
            
        elif format_type == 'commented':
            # Adiciona comentários explicativos
            if code_type == 'html':
                sections = ['head', 'body', 'style', 'script']
                for section in sections:
                    code = re.sub(
                        f'<{section}>', 
                        f'<!-- Início da seção {section} -->\n<{section}>', 
                        code
                    )
            
        return code.strip()
        
    def clean_and_validate(self, code: str, code_type: str) -> str:
        """
        Limpa e valida o código gerado.
        
        Args:
            code: Código gerado
            code_type: Tipo do código
            
        Returns:
            Código limpo e validado
        """
        if not code:
            return ''
            
        code = code.strip()
        
        if code_type == 'html':
            # Remove meta tags duplicadas
            code = re.sub(r'(<meta[^>]*>)\1+', r'\1', code)
            
            # Limita número de meta tags
            meta_tags = re.findall(r'<meta[^>]*>', code)
            if len(meta_tags) > 3:
                code = re.sub(r'<meta[^>]*>', '', code)
                code = re.sub(r'<head[^>]*>', '''<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">''', code)
            
            # Garante fechamento de tags
            if not code.strip().endswith('</html>'):
                if '</body>' not in code:
                    code = code.rstrip() + '\n</body>\n</html>'
                else:
                    code = code.rstrip() + '\n</html>'
                    
        elif code_type == 'python':
            # Remove docstrings duplicadas
            code = re.sub(r'""".*?"""\s*""".*?"""', '"""\\1"""', code, flags=re.S)
            
            # Garante codificação UTF-8
            if not re.search(r'#.*coding.*utf-8', code, re.I):
                code = '# -*- coding: utf-8 -*-\n' + code
                
        return code

"""
Sistema de Persistência de Configurações do Usuário
Gerencia preferências, temas, configurações de IA e histórico
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

class UserSettings:
    """Gerenciador de configurações persistentes do usuário"""
    
    def __init__(self, settings_file: str = "user_settings.json"):
        self.settings_file = settings_file
        self.settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Carrega configurações do arquivo ou cria padrões"""
        default_settings = {
            "theme": "dark",
            "language": "pt-BR",
            "ai_preferences": {
                "response_style": "balanced",  # balanced, creative, precise
                "code_generation": {
                    "style": "template_first",
                    "max_tokens": 2048,
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "frequency_penalty": 0.1,
                    "presence_penalty": 0.1
                },
                "chat": {
                    "max_history": 1000,
                    "context_window": 4096,
                    "temperature": 0.7,
                    "enable_web_search": True
                },
                "cache_settings": {
                    "enabled": True,
                    "max_size": 1000,
                    "ttl_hours": 24
                }
            },
            "ui_preferences": {
                "sidebar_collapsed": False,
                "auto_save": True,
                "show_line_numbers": True,
                "font_size": 14,
                "tab_size": 4
            },
            "workspace": {
                "last_files": [],
                "recent_projects": [],
                "favorite_templates": []
            },
            "notifications": {
                "show_toasts": True,
                "sound_enabled": True,
                "ai_status_alerts": True
            },
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge com padrões para novas configurações
                    default_settings.update(loaded_settings)
                    default_settings["last_updated"] = datetime.now().isoformat()
                    return default_settings
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"[UserSettings] Erro ao carregar configurações: {e}")
        
        return default_settings
    
    def save_settings(self) -> bool:
        """Salva configurações no arquivo"""
        try:
            self.settings["last_updated"] = datetime.now().isoformat()
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[UserSettings] Erro ao salvar configurações: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor de configuração usando notação de ponto"""
        keys = key.split('.')
        value = self.settings
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """Define valor de configuração usando notação de ponto"""
        keys = key.split('.')
        settings = self.settings
        
        try:
            # Navegar até o penúltimo nível
            for k in keys[:-1]:
                if k not in settings:
                    settings[k] = {}
                settings = settings[k]
            
            # Definir o valor final
            settings[keys[-1]] = value
            return True
        except Exception as e:
            print(f"[UserSettings] Erro ao definir configuração {key}: {e}")
            return False
    
    def update_theme(self, theme: str) -> bool:
        """Atualiza tema do usuário"""
        valid_themes = ["dark", "light", "auto"]
        if theme in valid_themes:
            return self.set("theme", theme)
        return False
    
    def update_language(self, language: str) -> bool:
        """Atualiza idioma do usuário"""
        valid_languages = ["pt-BR", "en-US", "es-ES"]
        if language in valid_languages:
            return self.set("language", language)
        return False
    
    def update_ai_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Atualiza preferências da IA"""
        current_prefs = self.get("ai_preferences", {})
        current_prefs.update(preferences)
        return self.set("ai_preferences", current_prefs)
    
    def update_ui_preferences(self, preferences: Dict[str, Any]) -> bool:
        """Atualiza preferências da interface"""
        current_prefs = self.get("ui_preferences", {})
        current_prefs.update(preferences)
        return self.set("ui_preferences", current_prefs)
    
    def add_recent_file(self, file_path: str) -> bool:
        """Adiciona arquivo ao histórico recente"""
        recent_files = self.get("workspace.last_files", [])
        
        # Remove se já existir
        if file_path in recent_files:
            recent_files.remove(file_path)
        
        # Adiciona no início
        recent_files.insert(0, file_path)
        
        # Limita a 10 arquivos
        recent_files = recent_files[:10]
        
        return self.set("workspace.last_files", recent_files)
    
    def add_favorite_template(self, template_name: str) -> bool:
        """Adiciona template aos favoritos"""
        favorites = self.get("workspace.favorite_templates", [])
        
        if template_name not in favorites:
            favorites.append(template_name)
            # Limita a 5 favoritos
            favorites = favorites[-5:]
            return self.set("workspace.favorite_templates", favorites)
        
        return True
    
    def get_workspace_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do workspace"""
        return {
            "total_files": len(self.get("workspace.last_files", [])),
            "favorite_templates": len(self.get("workspace.favorite_templates", [])),
            "created_at": self.get("created_at"),
            "last_updated": self.get("last_updated")
        }
    
    def reset_to_defaults(self) -> bool:
        """Reseta configurações para padrões"""
        try:
            if os.path.exists(self.settings_file):
                os.remove(self.settings_file)
            self.settings = self._load_settings()
            return True
        except Exception as e:
            print(f"[UserSettings] Erro ao resetar configurações: {e}")
            return False
    
    def export_settings(self, export_path: str) -> bool:
        """Exporta configurações para arquivo"""
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[UserSettings] Erro ao exportar configurações: {e}")
            return False
    
    def import_settings(self, import_path: str) -> bool:
        """Importa configurações de arquivo"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_settings = json.load(f)
                self.settings.update(imported_settings)
                return self.save_settings()
        except Exception as e:
            print(f"[UserSettings] Erro ao importar configurações: {e}")
            return False


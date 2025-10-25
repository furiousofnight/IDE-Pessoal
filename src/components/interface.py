class Interface:
    def __init__(self):
        self.panels = {
            'chat': None, 'preview': None, 'files': None
        }
        self.init_panels()
        print("Interface principal da IDE pronta.")
        # Ponto de integração: atualizar painel de arquivos com lista/back-end
        # Ponto de integração: preview dinâmico de código salvo/carregado

    def init_panels(self):
        self.panels['chat'] = 'Painel de chat pronto'
        self.panels['preview'] = 'Painel de preview de código pronto'
        self.panels['files'] = 'Painel de arquivos pronto'

    def show_panels(self):
        for name, desc in self.panels.items():
            print(f"Painel '{name}': {desc}")

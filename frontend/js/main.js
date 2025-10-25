// Atualiza painel do chat reativamente
async function update_chat_panel() {
  const msgList = document.getElementById('chat-messages');
  if (msgList) {
    try {
      const response = await fetch('/api/chat/history');
      if (response.ok) {
        const data = await response.json();
        if (data.history && Array.isArray(data.history)) {
          // Limpa mensagens existentes
          msgList.innerHTML = '';
          
          // Adiciona cada mensagem do histórico
          data.history.forEach(msg => {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${msg.tipo}`;
            
            if (msg.tipo === 'code') {
              // Se for código, usa formatação especial
              const pre = document.createElement('pre');
              const code = document.createElement('code');
              code.textContent = msg.mensagem;
              pre.appendChild(code);
              msgDiv.appendChild(pre);
              if (window.hljs) {
                hljs.highlightElement(code);
              }
            } else {
              // Mensagem normal
              msgDiv.textContent = msg.mensagem;
            }
            
            msgList.appendChild(msgDiv);
          });
        }
      }
    } catch (error) {
      console.error('Erro ao carregar histórico:', error);
    }
    
    // Rola para a última mensagem
    msgList.scrollTop = msgList.scrollHeight;
  }
}

// Atualiza visualização de preview reativamente
function refresh_preview() {
  const block = document.getElementById('code');
  if (block) {
    if(window.hljs){hljs.highlightElement(block);}
  }
}
// Manipula lista local de arquivos salvos pelo usuário
let savedFiles = [];
let lastPromptSent = '';
let lastPromptForCode = '';
let statusCheckInterval = null;
let isPageVisible = true;
let userSettings = {};

// Alterna barra lateral (sidebar) expandida/contraída
function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('collapsed');
}

// Carrega configurações do usuário
async function loadUserSettings() {
  try {
    const response = await fetch('/api/settings');
    if (response.ok) {
      userSettings = await response.json();
      applyUserSettings();
    }
  } catch (error) {
    console.warn('Erro ao carregar configurações:', error);
  }
}

// Aplica configurações do usuário
function applyUserSettings() {
  // Aplicar tema
  const theme = userSettings.theme || 'dark';
  if (theme !== currentTheme) {
    toggleTheme(theme);
  }
  
  // Aplicar preferências da sidebar
  const sidebarCollapsed = userSettings.ui_preferences?.sidebar_collapsed || false;
  if (sidebarCollapsed) {
    document.querySelector('.sidebar').classList.add('collapsed');
  }
  
  // Aplicar outras configurações...
  console.log('Configurações aplicadas:', userSettings);
}

// Salva configurações do usuário
async function saveUserSettings(settings) {
  try {
    const response = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    
    if (response.ok) {
      const result = await response.json();
      if (result.success) {
        userSettings = { ...userSettings, ...settings };
        toast('Configurações salvas!');
      }
    }
  } catch (error) {
    console.error('Erro ao salvar configurações:', error);
    toast('Erro ao salvar configurações');
  }
}

// Alterna tema e salva configuração
function toggleTheme(theme = null) {
  if (!theme) {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
  } else {
    currentTheme = theme;
  }
  
  document.body.className = currentTheme;
  
  // Atualizar ícone do botão
  const themeBtn = document.getElementById('btn-theme');
  if (themeBtn) {
    themeBtn.textContent = currentTheme === 'dark' ? '🌙' : '☀️';
  }
  
  // Salvar configuração
  saveUserSettings({ theme: currentTheme });
}

// Ao carregar a página, inicializa tabs, listeners de input e status da IA
// Foco automático no campo do chat ao abrir a aba
// Periodicamente verifica status da IA backend
// Também aplica destaques a blocos de código, placeholders de preview e histórico
document.addEventListener('DOMContentLoaded', () => {
  // Carregar configurações do usuário primeiro
  loadUserSettings();
  
  document.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = function() {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      this.classList.add('active');
      document.querySelector(this.dataset.tab).classList.add('active');
      // Foco no input do chat se abrir o chat
      if (this.dataset.tab === '#tab-chat') {
        setTimeout(()=>{document.getElementById('input-msg').focus();}, 140);
      }
    };
  });
  
  document.getElementById('toggle-sidebar').onclick = toggleSidebar;
  
  // Botão de tema
  const themeBtn = document.getElementById('btn-theme');
  if (themeBtn) {
    themeBtn.onclick = () => toggleTheme();
  }
  
  // Input foca por padrão
  document.getElementById('input-msg').focus();
  // Envio com ENTER, nova linha com Shift+ENTER
  const input = document.getElementById('input-msg');
  // Debounce para envio
  let debounceTimer = null;
  function debouncedSendMessage(){
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(sendMessage, 350);
  }
  input.addEventListener('keydown', function(e){
    if (e.key==='Enter' && !e.shiftKey) {
      e.preventDefault();
      debouncedSendMessage();
    }
  });
  // highlight all statically loaded code blocks
  if(window.hljs){hljs.highlightAll();}
  showPreviewPlaceholder();
  showHistoryPlaceholder();
  updateIAStatus();
  startStatusPolling();
});

// Exibe mensagem toast personalizada (feedback instantâneo ao usuário)
function toast(msg) {
  const el = document.getElementById('overlay-toast');
  el.innerText = msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 2850);
}

// Performance logging para requisições
function logPerformance(start, end, type) {
  const duration = end - start;
  console.log(`[Performance] ${type} request took ${duration}ms`);
  if (duration > 2000) {
    toast(`⚠️ Resposta lenta (${Math.round(duration/1000)}s)`);
  }
}

function sendMessage() {
  const input = document.getElementById('input-msg');
  const msg = input.value;
  if (!msg || !msg.trim()) return;
  
  const startTime = performance.now();
  
  // Validação robusta de entrada
  if (msg.length > 2000) {
    toast('Mensagem muito longa. Limite de 2000 caracteres.');
    return;
  }
  
  const sanitizedMsg = msg.trim().substring(0, 2000);
  
  showCodePreview('');
  appendBubble('user', sanitizedMsg);
  
  const loadingBubble = appendBubble('ia', '<div class="loading-spinner">🤖 IA está pensando...</div>');
  
  fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ 
      message: sanitizedMsg,
      force_new: true
    })
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    const endTime = performance.now();
    logPerformance(startTime, endTime, 'Chat');
    
    if (loadingBubble && loadingBubble.parentNode) {
      loadingBubble.parentNode.removeChild(loadingBubble);
    }
    
    if (data.error) {
      toast(data.error);
      updateIAStatus();
      return;
    }

    if (!data.result) {
      toast('A IA não conseguiu responder. Tente reformular.');
    } else {
      const trimmedResult = data.result.trim();
      if (trimmedResult) {
        appendBubble('ia', trimmedResult);
      }
    }

    if (data.code !== undefined) {
      if (!data.code || !data.code.trim()) {
        showCodePreview('');
        toast('Nenhum código gerado.');
      } else {
        showCodePreview(data.code, data.code_type);
        lastPromptForCode = sanitizedMsg;
        toast('Código gerado com sucesso!');
        switchToTab('tab-code');
      }
    }
  })
  .catch(error => {
    const endTime = performance.now();
    logPerformance(startTime, endTime, 'Error');
    
    console.error('Erro detalhado:', error);
    
    if (loadingBubble && loadingBubble.parentNode) {
      loadingBubble.parentNode.removeChild(loadingBubble);
    }
    
    toast('Erro de conexão. Tente novamente.');
    showCodePreview('');
    updateIAStatus();
  });
  
  input.value = '';
  setTimeout(() => input.focus(), 50);
}

// Adiciona uma mensagem no chat, formatando quem enviou (usuário ou IA)
function appendBubble(role, text) {
  const msgList = document.getElementById('chat-messages');
  const message = document.createElement('div');
  message.className = 'message ' + (role === 'ia' ? 'assistant' : role);
  
  if (typeof text === 'string' && text.trim().startsWith('```')) {
    // Se for bloco de código
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    // Remove os marcadores de código e linguagem
    const codeText = text.replace(/^```\w*\n/, '').replace(/```$/, '');
    code.textContent = codeText;
    pre.appendChild(code);
    message.appendChild(pre);
    if (window.hljs) {
      hljs.highlightElement(code);
    }
  } else {
    // Mensagem normal
    message.innerHTML = text.replace(/\n/g,'<br>');
  }
  
  const time = document.createElement('span');
  time.className = 'timestamp';
  time.innerText = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
  message.appendChild(time);
  
  msgList.appendChild(message);
  msgList.scrollTop = msgList.scrollHeight;
  return message; // Retorna referência para remoção posterior
}

// Recebe code e tipo (opcional)
function showCodePreview(code, tipo) {
  const block = document.getElementById('code');
  if (!code || !code.trim()) {
    block.innerHTML = '<span style="opacity:.38;font-style:italic;">Nenhum código gerado pela IA para esse pedido.<br>Tente especificar melhor ou faça outro pedido!</span>';
    lastPromptForCode = '';
    console.log('Preview limpo e lastPromptForCode resetado');
    return;
  }
  // Ajuste: seta linguagem de código
  block.className = `hljs language-${tipo || 'python'}`;
  block.textContent = code;
  if(window.hljs){hljs.highlightElement(block);}
  console.log('Código atualizado no preview:', code.substring(0, 50) + '...');
}
// Limpa o preview e reseta estados
function clearPreview() {
  const block = document.getElementById('code');
  block.innerHTML = '<span style="opacity:.36;font-style:italic;">Gere um código para visualização aqui.</span>';
  lastPromptForCode = '';
  console.log('Preview limpo manualmente');
  toast('Preview limpo');
}

// Rejeita o código atual, limpa preview e notifica backend
async function rejectCode() {
  if (!document.getElementById('code').textContent.trim()) {
    toast('Nenhum código para rejeitar');
    return;
  }

  try {
    // Limpar cache do prompt no backend
    if (lastPromptSent) {
      await fetch('/api/clear_prompt_cache', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: lastPromptSent })
      });
    }
    
    clearPreview();
    toast('Código rejeitado e cache limpo');
    
  } catch (error) {
    console.error('Erro ao rejeitar código:', error);
    toast('Erro ao rejeitar código');
  }
}

// Placeholder mostrado quando não há código
function showPreviewPlaceholder() {
  clearPreview();
}
// Placeholder mostrado quando não há arquivos/histórico
function showHistoryPlaceholder() {
  const preview = document.getElementById('file-preview');
  preview.innerHTML = '<span style="opacity:.38;font-style:italic;">Nenhum histórico por enquanto. Salve códigos para ver aqui.</span>';
}

// Troca entre as abas principais (chat, preview código, histórico)
function switchToTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const tabBtn = document.querySelector('.tab[data-tab="#'+tabId+'"]');
  if(tabBtn) tabBtn.classList.add('active');
  document.getElementById(tabId).classList.add('active');
  if (tabId==='tab-chat'){
    setTimeout(()=>{document.getElementById('input-msg').focus();}, 100);
  }
}

// Removido: função generateCode() e qualquer referência ao botão ou chamada direta do endpoint code.
// O preview de código só será atualizado quando resposta do chat trouxer código válido.

// Lê última resposta do chat em voz usando TTS do navegador
function speakLastMessage() {
  const messages = document.getElementById('chat-messages').children;
  if (!messages.length) return;
  const last = messages[messages.length - 1];
  let lastMsg = last.innerText || last.textContent;
  const port = /[ãêõçáéíóúâôà]|você|exemplo|faça|bom dia|olá|saúde/i.test(lastMsg);
  let voice = null;
  if ('speechSynthesis' in window) {
    const synth = window.speechSynthesis;
    const voices = synth.getVoices();
    if (voices.length > 0) {
      voice = voices.find(v=> v.lang && v.lang.toLowerCase().includes(port ? 'pt-br' : 'en')) || null;
    }
    if(port && !voice) voice = voices.find(v=>v.lang && v.lang.startsWith('pt')) || null;
    const utter = new SpeechSynthesisUtterance(lastMsg);
    if(voice) utter.voice = voice;
    utter.lang = voice ? voice.lang : (port ? 'pt-BR' : 'en-US');
    utter.rate = 1.05;
    utter.volume = 1.0;
    synth.speak(utter);
  } else {
    toast('Seu navegador não suporta TTS.');
  }
}

// Salva código gerado em arquivo na pasta resultados-modelo/
async function saveGeneratedCode() {
  const code = document.getElementById('code').innerText;
  if (!code.trim()) {
    toast('Nenhum código para salvar.');
    return;
  }

  const filename = prompt('Nome do arquivo para salvar:', 'codigo_ia_' + (savedFiles.length+1) + '.html');
  if (!filename) return;

  try {
    // Salvar no backend
    const response = await fetch('/api/save_code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, filename })
    });

    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || 'Erro ao salvar arquivo');
    }

    // Adicionar à lista local
    savedFiles.push({name: filename, content: code, path: data.file_path});
    updateSavedFiles();
    
    toast('Código salvo com sucesso em: ' + data.file_path);
    showCodePreview('', ''); // Limpa preview após salvar

    // Limpa cache do prompt no backend
    if (lastPromptSent) {
      await fetch('/api/clear_prompt_cache', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: lastPromptSent })
      });
    }
  } catch (error) {
    console.error('Erro ao salvar:', error);
    toast('Erro ao salvar arquivo: ' + error.message);
  }
}

// Atualiza painel de arquivos salvos
function updateSavedFiles() {
  const panel = document.getElementById('saved-files');
  if (!savedFiles.length) {
    panel.innerText = 'Nenhum arquivo salvo.';
    return;
  }
  panel.innerHTML = '';
  savedFiles.forEach((f, idx) => {
    const el = document.createElement('div');
    el.innerText = f.name;
    el.style.cursor = 'pointer';
    el.onclick = function() { showFilePreview(idx); };
    panel.appendChild(el);
  });
}

// Mostra arquivo salvo na pré-visualização/histórico
function showFilePreview(idx) {
  const file = savedFiles[idx];
  const preview = document.getElementById('file-preview');
  preview.style.display = 'block';
  preview.innerHTML = `<b>${file.name}</b><pre>${file.content.replace(/</g,'&lt;')}</pre>`;
  showCodePreview('', ''); // Limpa preview principal ao visualizar arquivo salvo
}

// Otimização: polling inteligente com debounce e pausa quando página não visível
function startStatusPolling() {
  if (statusCheckInterval) return; // Evita múltiplos intervalos
  statusCheckInterval = setInterval(() => {
    if (isPageVisible) {
      updateIAStatus();
    }
  }, 5000); // Reduzido para 5s para melhor responsividade
}

// Pausar polling quando página não está visível (performance)
document.addEventListener('visibilitychange', () => {
  isPageVisible = !document.hidden;
});

// Atualiza status do backend IA local periodicamente
function updateIAStatus() {
  fetch('/api/status')
    .then(r=>r.json())
    .then(status=>{
      const el = document.getElementById('ia-status');
      if (!el) return;
      el.textContent = (status.status ? 'IA Local: Online' : 'IA Local: Offline');
      el.style.color = (status.status ? '#6cfaab' : '#ff4040');
    }).catch(()=>{
      const el = document.getElementById('ia-status');
      if (el) {
        el.textContent = 'IA Local: Offline';
        el.style.color = '#ff4040';
      }
    })
}

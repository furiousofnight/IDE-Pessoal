"""
Configuração e otimização dos modelos LLM.
"""
import os
import psutil
from typing import Dict, Any
import torch
import logging
from llama_cpp import Llama

logger = logging.getLogger("model_setup")

def optimize_model_params(model_type: str) -> Dict[str, Any]:
    """Otimiza parâmetros do modelo baseado no hardware disponível."""
    
    # Detecta recursos disponíveis
    cpu_count = os.cpu_count() or 4
    ram = psutil.virtual_memory()
    has_gpu = torch.cuda.is_available()
    
    # Parâmetros base otimizados
    params = {
        'n_ctx': 4096,  # Aumentado para melhor contexto
        'n_threads': min(12, cpu_count),  # Mais threads para performance
        'n_batch': 512,  # Aumentado para melhor throughput
        'use_mmap': True,  # Manter mmap
        'use_mlock': ram.available > 8 * 1024 * 1024 * 1024,  # Ativar se tiver RAM suficiente
        'verbose': False,
        'n_gpu_layers': 32 if has_gpu else 0,  # Usa GPU se disponível
        'f16_kv': True,  # Ativa otimização de memória
        'embedding': True  # Habilita embeddings para melhor contexto
    }
    
    # Otimizações específicas por tipo
    if model_type == 'chat':
        params.update({
            'n_gpu_layers': 32 if has_gpu else 0,  # Mais layers na GPU para chat
            'rope_scaling': {"type": "linear", "factor": 2.0},  # Melhor processamento de contexto
            'logits_all': True,  # Habilita probability sampling
            'embedding': True  # Permite embeddings para cache
        })
    else:  # code
        params.update({
            'n_gpu_layers': 24 if has_gpu else 0,  # Menos layers na GPU para código
            'rope_scaling': {"type": "linear", "factor": 4.0},  # Contexto ainda maior
            'logits_all': False,  # Não necessário para código
            'embedding': False  # Não necessário para código
        })
    
    logger.info(f"Parâmetros otimizados para modelo {model_type}: {params}")
    return params

def load_optimized_model(model_path: str, model_type: str) -> Llama:
    """Carrega modelo com parâmetros otimizados."""
    try:
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo não encontrado: {model_path}")
        
        # Obtém parâmetros otimizados
        params = optimize_model_params(model_type)
        
        # Garante que o modelo anterior foi liberado
        import gc
        gc.collect()
        
        # Carrega modelo com parâmetros otimizados
        model = Llama(model_path=model_path, **params)
        
        # Força uma inferência teste para validar o modelo
        test_prompt = "Teste de modelo."
        try:
            model(test_prompt, max_tokens=10)
            logger.info(f"Modelo {model_type} carregado e testado com sucesso")
            return model
        except Exception as e:
            logger.error(f"Falha no teste do modelo {model_type}: {e}")
            del model
            gc.collect()
            return None
        
    except Exception as e:
        logger.error(f"Erro ao carregar modelo {model_type}: {e}")
        return None

def get_optimal_generation_params(model_type: str, query_length: int) -> Dict[str, Any]:
    """Calcula parâmetros ótimos para geração baseado no tipo e tamanho da query."""
    
    ram = psutil.virtual_memory()
    is_complex = query_length > 100
    
    if model_type == 'chat':
        return {
            'max_tokens': min(4096, int(ram.available / (2 * 1024 * 1024))),  # 2MB por token
            'temperature': 0.7 if is_complex else 0.8,
            'top_p': 0.9,
            'repeat_penalty': 1.1,
            'top_k': 40,
            'presence_penalty': 0.05
        }
    else:  # code
        return {
            'max_tokens': 4096,  # Aumentado significativamente
            'temperature': 0.3,  # Ajustado para mais criatividade
            'top_p': 0.8,        # Mais flexível
            'repeat_penalty': 0.9,  # Menos restritivo
            'presence_penalty': 0.1,  # Leve penalidade
            'top_k': 50,         # Mais abrangente
            'stop': [
                '<|endoftext|>', 
                '```', 
                '"""', 
                "'''", 
                '# End of code', 
                '// End of code'
            ]  # Múltiplos stop tokens
        }
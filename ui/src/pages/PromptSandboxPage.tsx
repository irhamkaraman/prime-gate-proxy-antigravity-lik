import React, { useState, useEffect, useRef } from 'react';
import { ModelInfo } from '../types';
import { useToast } from '../context/ToastContext';
import { Play, Square, Sparkles, Copy, Check, Terminal, Cpu } from 'lucide-react';

export const PromptSandboxPage: React.FC = () => {
  const { showToast } = useToast();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [apiProtocol, setApiProtocol] = useState<'openai' | 'anthropic'>('openai');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.8-flash');
  const [systemPrompt, setSystemPrompt] = useState<string>('You are an expert AI software engineer. Provide clear, precise, and practical code solutions.');
  const [userPrompt, setUserPrompt] = useState<string>('Write a Python function to compute the SHA-256 hash of a file efficiently using chunks.');
  const [temperature, setTemperature] = useState<number>(0.7);
  const [maxTokens, setMaxTokens] = useState<number>(2048);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [output, setOutput] = useState<string>('');
  const [ttftMs, setTtftMs] = useState<number | null>(null);
  const [totalTimeMs, setTotalTimeMs] = useState<number | null>(null);
  const [tokenEstimate, setTokenEstimate] = useState<number>(0);
  const [copied, setCopied] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const preselected = sessionStorage.getItem('selected_sandbox_model');
    if (preselected) {
      setSelectedModel(preselected);
      sessionStorage.removeItem('selected_sandbox_model');
    }

    fetch('/v1/models')
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.data)) {
          setModels(data.data);
          if (preselected && data.data.some((m: ModelInfo) => m.id === preselected)) {
            setSelectedModel(preselected);
          } else if (data.data.length > 0 && !data.data.some((m: ModelInfo) => m.id === (preselected || selectedModel))) {
            setSelectedModel(data.data[0].id);
          }
        }
      })
      .catch(err => console.error('Failed to load models for sandbox:', err));
  }, []);

  const handleSendPrompt = async () => {
    if (!userPrompt.trim()) {
      showToast('Please enter a user prompt', 'warning');
      return;
    }

    setIsLoading(true);
    setOutput('');
    setTtftMs(null);
    setTotalTimeMs(null);
    setTokenEstimate(0);

    const startTime = Date.now();
    let firstTokenTime: number | null = null;
    let accumulatedText = '';

    abortControllerRef.current = new AbortController();

    try {
      let endpointUrl = '/v1/chat/completions';
      let headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer prime-gate-proxy',
      };
      let requestBody: Record<string, any> = {};

      if (apiProtocol === 'anthropic') {
        endpointUrl = '/v1/messages';
        headers = {
          'Content-Type': 'application/json',
          'x-api-key': 'prime-gate-proxy',
          'anthropic-version': '2023-06-01',
        };
        requestBody = {
          model: selectedModel,
          system: systemPrompt.trim() ? systemPrompt.trim() : undefined,
          messages: [{ role: 'user', content: userPrompt.trim() }],
          temperature,
          max_tokens: maxTokens,
          stream: true,
        };
      } else {
        const messages = [];
        if (systemPrompt.trim()) {
          messages.push({ role: 'system', content: systemPrompt.trim() });
        }
        messages.push({ role: 'user', content: userPrompt.trim() });
        requestBody = {
          model: selectedModel,
          messages,
          temperature,
          max_tokens: maxTokens,
          stream: true,
        };
      }

      const response = await fetch(endpointUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error?.message || errorData.detail || `HTTP ${response.status}: Inference error`);
      }

      if (!response.body) {
        throw new Error('Readable stream not supported');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) continue;

          if (trimmed === 'data: [DONE]') {
            break;
          }

          if (trimmed.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(trimmed.slice(6));

              // Case A: Anthropic SSE Protocol
              if (apiProtocol === 'anthropic') {
                if (parsed.type === 'content_block_delta' && parsed.delta?.text) {
                  const delta = parsed.delta.text;
                  if (firstTokenTime === null) {
                    firstTokenTime = Date.now();
                    setTtftMs(firstTokenTime - startTime);
                  }
                  accumulatedText += delta;
                  setOutput(accumulatedText);
                  setTokenEstimate(Math.round(accumulatedText.length / 4));
                }
              } else {
                // Case B: OpenAI SSE Protocol
                const delta = parsed.choices?.[0]?.delta?.content || '';
                if (delta) {
                  if (firstTokenTime === null) {
                    firstTokenTime = Date.now();
                    setTtftMs(firstTokenTime - startTime);
                  }
                  accumulatedText += delta;
                  setOutput(accumulatedText);
                  setTokenEstimate(Math.round(accumulatedText.length / 4));
                }
              }
            } catch (err) {
              // Ignore partial JSON
            }
          }
        }
      }

      setTotalTimeMs(Date.now() - startTime);
      showToast(`Generation complete (${apiProtocol.toUpperCase()} protocol)`, 'success');
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        showToast((err as Error).message || 'Generation failed', 'error');
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsLoading(false);
      showToast('Generation cancelled', 'info');
    }
  };

  const handleCopyOutput = () => {
    if (!output) return;
    navigator.clipboard.writeText(output).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      showToast('Output copied to clipboard', 'success');
    });
  };

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: 24,
          alignItems: 'start',
        }}
      >
        {/* Left Column: Prompt Controls */}
        <div className="glass-card" style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#ffffff', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Terminal size={18} color="#f59e0b" />
            <span>Parameters & Config</span>
          </h2>

          {/* Protocol Endpoint Selector */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6, display: 'block' }}>
              API Protocol & Endpoint
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <button
                type="button"
                onClick={() => setApiProtocol('openai')}
                style={{
                  padding: '9px 12px',
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: apiProtocol === 'openai' ? '1px solid #10b981' : '1px solid rgba(255,255,255,0.08)',
                  background: apiProtocol === 'openai' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255,255,255,0.03)',
                  color: apiProtocol === 'openai' ? '#34d399' : '#a8a29e',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  transition: 'all 0.15s ease'
                }}
              >
                <span>OpenAI Protocol</span>
                <span style={{ fontSize: 10, opacity: 0.7, fontFamily: 'var(--font-mono)' }}>/v1/chat/completions</span>
              </button>

              <button
                type="button"
                onClick={() => setApiProtocol('anthropic')}
                style={{
                  padding: '9px 12px',
                  borderRadius: 8,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: apiProtocol === 'anthropic' ? '1px solid #f59e0b' : '1px solid rgba(255,255,255,0.08)',
                  background: apiProtocol === 'anthropic' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(255,255,255,0.03)',
                  color: apiProtocol === 'anthropic' ? '#fbbf24' : '#a8a29e',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  transition: 'all 0.15s ease'
                }}
              >
                <span>Anthropic Protocol</span>
                <span style={{ fontSize: 10, opacity: 0.7, fontFamily: 'var(--font-mono)' }}>/v1/messages</span>
              </button>
            </div>
          </div>

          {/* Model Selector */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6, display: 'block' }}>
              Target Model
            </label>
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              style={{
                width: '100%',
                background: '#181310',
                border: '1px solid rgba(168, 162, 158, 0.2)',
                borderRadius: 8,
                padding: '10px 12px',
                color: '#fafaf9',
                fontSize: 13,
                fontFamily: 'var(--font-mono)',
                outline: 'none',
              }}
            >
              {models.length > 0 ? (
                models.map(m => (
                  <option key={m.id} value={m.id}>
                    {m.id} ({m.owned_by || 'google-antigravity'})
                  </option>
                ))
              ) : (
                <>
                  <option value="gemini-3.8-flash">gemini-3.8-flash</option>
                  <option value="gemini-3.8-flash-high">gemini-3.8-flash-high</option>
                  <option value="gemini-3.8-pro">gemini-3.8-pro</option>
                  <option value="claude-3-7-sonnet">claude-3-7-sonnet</option>
                </>
              )}
            </select>
          </div>

          {/* System Instructions */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6, display: 'block' }}>
              System Prompt (Optional)
            </label>
            <textarea
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
              rows={3}
              style={{
                width: '100%',
                background: '#181310',
                border: '1px solid rgba(168, 162, 158, 0.2)',
                borderRadius: 8,
                padding: '10px 12px',
                color: '#fafaf9',
                fontSize: 13,
                resize: 'vertical',
                outline: 'none',
              }}
              placeholder="Define persona or role..."
            />
          </div>

          {/* User Prompt */}
          <div>
            <label style={{ fontSize: 12, fontWeight: 600, color: '#a8a29e', marginBottom: 6, display: 'block' }}>
              User Message
            </label>
            <textarea
              value={userPrompt}
              onChange={e => setUserPrompt(e.target.value)}
              rows={5}
              style={{
                width: '100%',
                background: '#181310',
                border: '1px solid rgba(168, 162, 158, 0.2)',
                borderRadius: 8,
                padding: '10px 12px',
                color: '#fafaf9',
                fontSize: 13,
                resize: 'vertical',
                outline: 'none',
              }}
              placeholder="Enter your prompt here..."
            />
          </div>

          {/* Sliders: Temperature & Max Tokens */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#a8a29e', marginBottom: 4 }}>
                <span>Temperature</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#fbbf24' }}>{temperature.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                value={temperature}
                onChange={e => setTemperature(parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: '#f59e0b' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#a8a29e', marginBottom: 4 }}>
                <span>Max Tokens</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#fbbf24' }}>{maxTokens}</span>
              </div>
              <input
                type="range"
                min="256"
                max="8192"
                step="256"
                value={maxTokens}
                onChange={e => setMaxTokens(parseInt(e.target.value, 10))}
                style={{ width: '100%', accentColor: '#f59e0b' }}
              />
            </div>
          </div>

          {/* Action Button */}
          <div style={{ marginTop: 10 }}>
            {isLoading ? (
              <button
                onClick={handleStop}
                className="btn btn-danger"
                style={{ width: '100%', padding: '12px 16px' }}
              >
                <Square size={16} />
                <span>Stop Streaming</span>
              </button>
            ) : (
              <button
                onClick={handleSendPrompt}
                className="btn btn-primary"
                style={{ width: '100%', padding: '12px 16px' }}
              >
                <Play size={16} />
                <span>Run Inference</span>
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Streaming Output Window */}
        <div className="glass-card" style={{ padding: '24px 28px', minHeight: 520, display: 'flex', flexDirection: 'column' }}>
          {/* Output Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
              paddingBottom: 16,
              marginBottom: 16,
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <Cpu size={18} color="#10b981" style={{ flexShrink: 0 }} />
              <h3 style={{ fontSize: 15, fontWeight: 700, color: '#ffffff', wordBreak: 'break-word' }}>
                Streaming Output ({selectedModel})
              </h3>
              <span
                className={apiProtocol === 'anthropic' ? 'badge badge-amber' : 'badge badge-emerald'}
                style={{ fontSize: 11, fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}
              >
                {apiProtocol === 'anthropic' ? 'Anthropic /v1/messages' : 'OpenAI /v1/chat/completions'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {ttftMs !== null && (
                <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  TTFT: {ttftMs}ms
                </span>
              )}
              {totalTimeMs !== null && (
                <span className="badge badge-emerald" style={{ fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  Total: {totalTimeMs}ms
                </span>
              )}
              {tokenEstimate > 0 && (
                <span className="badge badge-amber" style={{ fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
                  ~{tokenEstimate} tokens
                </span>
              )}
              {output && (
                <button
                  onClick={handleCopyOutput}
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '5px 10px', whiteSpace: 'nowrap' }}
                >
                  {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                  <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
              )}
            </div>
          </div>

          {/* Response Text Box */}
          <div
            style={{
              flex: 1,
              background: '#090807',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: 10,
              padding: 20,
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              color: '#fafaf9',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              overflowY: 'auto',
              maxHeight: 550,
            }}
          >
            {output ? (
              output
            ) : (
              <span style={{ color: '#57534e', fontStyle: 'italic' }}>
                {isLoading ? 'Connecting to Google Antigravity stream...' : 'Response stream will appear here when you click "Run Inference".'}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

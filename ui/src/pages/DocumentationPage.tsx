import React, { useState } from 'react';
import { useToast } from '../context/ToastContext';
import { BookOpen, Copy, Check, Terminal, Code2, Server, ExternalLink, Sparkles } from 'lucide-react';

export const DocumentationPage: React.FC = () => {
  const { showToast } = useToast();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyCode = (id: string, text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      showToast('Code snippet copied to clipboard', 'success');
      setTimeout(() => setCopiedId(null), 2000);
    });
  };

  const curlChatSnippet = `curl http://127.0.0.1:52111/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer prime-gate-proxy" \\
  -d '{
    "model": "gemini-3.8-flash",
    "messages": [
      {"role": "user", "content": "Explain binary search in one concise paragraph."}
    ],
    "stream": true
  }'`;

  const pythonSnippet = `import openai

client = openai.OpenAI(
    base_url="http://127.0.0.1:52111/v1",
    api_key="prime-gate-proxy"
)

response = client.chat.completions.create(
    model="gemini-3.8-flash",
    messages=[{"role": "user", "content": "Hello from Python!"}],
    stream=True
)

for chunk in response:
    content = chunk.choices[0].delta.content or ""
    print(content, end="", flush=True)`;

  const tsSnippet = `import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "http://127.0.0.1:52111/v1",
  apiKey: "prime-gate-proxy",
});

async function main() {
  const stream = await openai.chat.completions.create({
    model: "gemini-3.8-flash",
    messages: [{ role: "user", content: "Hello from TypeScript!" }],
    stream: true,
  });

  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }
}

main();`;

  const healthSnippet = `curl -s http://127.0.0.1:52111/v1/health | jq .`;

  return (
    <div style={{ padding: '28px 32px', display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 1080 }}>
      {/* Intro Header */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <BookOpen size={24} color="#f59e0b" />
          <h2 style={{ fontSize: 18, fontWeight: 700, color: '#ffffff' }}>
            Integration & Usage Guide
          </h2>
        </div>
        <p style={{ fontSize: 13, color: '#a8a29e', marginTop: 8, lineHeight: 1.6 }}>
          Prime Gate Antigravity acts as a drop-in local OpenAI-compatible API gateway. Any tool, library, or application that accepts a custom OpenAI Base URL can seamlessly consume high-speed Google Antigravity inference.
        </p>
      </div>

      {/* Client Configuration (Cursor / OpenCode / Continue) */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: '#ffffff', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Server size={18} color="#38bdf8" />
          <span>IDE & Extension Configuration</span>
        </h3>
        <p style={{ fontSize: 13, color: '#a8a29e', marginBottom: 16 }}>
          Configure your preferred development assistant with these parameters:
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 14 }}>
          <div style={{ background: '#090807', padding: '14px 18px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#78716c', textTransform: 'uppercase' }}>OpenAI Base URL</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#f59e0b', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
              http://127.0.0.1:52111/v1
            </div>
          </div>
          <div style={{ background: '#090807', padding: '14px 18px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#78716c', textTransform: 'uppercase' }}>API Key</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#d6d3d1', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
              prime-gate-proxy
            </div>
          </div>
          <div style={{ background: '#090807', padding: '14px 18px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#78716c', textTransform: 'uppercase' }}>Recommended Models</div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#34d399', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
              gemini-3.8-flash, gemini-3.8-pro
            </div>
          </div>
        </div>
      </div>

      {/* v1.2.0 Enterprise Engine Architecture */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: '#ffffff', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={18} color="#f59e0b" />
          <span>v1.2.0 Enterprise Engine Capabilities</span>
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
          <div style={{ background: '#090807', padding: 16, borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#34d399' }}>1. Smart Context Compactor</div>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 6, lineHeight: 1.5 }}>
              Automatically trims historical tool call logs (&gt;3 turns old) while preserving system instructions and recent context, reducing 30k–100k prompts by 50–70%.
            </p>
          </div>
          <div style={{ background: '#090807', padding: 16, borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#38bdf8' }}>2. Mid-Flight Transparent Failover</div>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 6, lineHeight: 1.5 }}>
              Catches upstream HTTP 429 quota exhaustion and rotates to the next healthy Google account before emitting the first stream token—zero client drops.
            </p>
          </div>
          <div style={{ background: '#090807', padding: 16, borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#f43f5e' }}>3. AI Runaway Loop Sentinel</div>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 6, lineHeight: 1.5 }}>
              Detects infinite loops where agents repeat identical failing tool calls (&ge;3 times) and injects corrective system interventions to halt quota drain.
            </p>
          </div>
          <div style={{ background: '#090807', padding: 16, borderRadius: 10, border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fbbf24' }}>4. Economic Value Simulator</div>
            <p style={{ fontSize: 12, color: '#a8a29e', marginTop: 6, lineHeight: 1.5 }}>
              Calculates equivalent commercial API savings (GPT-4o / Claude 3.5 Sonnet benchmark) in USD and IDR directly on the live dashboard.
            </p>
          </div>
        </div>
      </div>


      {/* Code Snippets Section */}
      <div className="glass-card" style={{ padding: '24px 28px' }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, color: '#ffffff', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Code2 size={18} color="#10b981" />
          <span>Code Examples</span>
        </h3>

        {/* Python Snippet */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e7e5e4' }}>Python SDK (openai)</span>
            <button
              onClick={() => copyCode('python', pythonSnippet)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '4px 8px' }}
            >
              {copiedId === 'python' ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
              <span>{copiedId === 'python' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre style={{ background: '#090807', padding: 16, borderRadius: 8, overflowX: 'auto', fontSize: 12, color: '#d6d3d1', border: '1px solid rgba(255,255,255,0.06)' }}>
            <code>{pythonSnippet}</code>
          </pre>
        </div>

        {/* TypeScript Snippet */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e7e5e4' }}>Node.js / TypeScript SDK</span>
            <button
              onClick={() => copyCode('ts', tsSnippet)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '4px 8px' }}
            >
              {copiedId === 'ts' ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
              <span>{copiedId === 'ts' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre style={{ background: '#090807', padding: 16, borderRadius: 8, overflowX: 'auto', fontSize: 12, color: '#d6d3d1', border: '1px solid rgba(255,255,255,0.06)' }}>
            <code>{tsSnippet}</code>
          </pre>
        </div>

        {/* cURL Chat Snippet */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e7e5e4' }}>cURL (Streaming Chat Completions)</span>
            <button
              onClick={() => copyCode('curl', curlChatSnippet)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '4px 8px' }}
            >
              {copiedId === 'curl' ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
              <span>{copiedId === 'curl' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre style={{ background: '#090807', padding: 16, borderRadius: 8, overflowX: 'auto', fontSize: 12, color: '#d6d3d1', border: '1px solid rgba(255,255,255,0.06)' }}>
            <code>{curlChatSnippet}</code>
          </pre>
        </div>

        {/* Health API cURL */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#e7e5e4' }}>cURL (Health & Sentinel Diagnostics)</span>
            <button
              onClick={() => copyCode('health', healthSnippet)}
              className="btn btn-secondary btn-sm"
              style={{ padding: '4px 8px' }}
            >
              {copiedId === 'health' ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
              <span>{copiedId === 'health' ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
          <pre style={{ background: '#090807', padding: 16, borderRadius: 8, overflowX: 'auto', fontSize: 12, color: '#d6d3d1', border: '1px solid rgba(255,255,255,0.06)' }}>
            <code>{healthSnippet}</code>
          </pre>
        </div>
      </div>
    </div>
  );
};

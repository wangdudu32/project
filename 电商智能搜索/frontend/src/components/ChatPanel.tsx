import {
  ArrowDownLeft,
  ArrowUp,
  ArrowUpRight,
  LoaderCircle,
  MessageCircle,
  Plus,
  Scale,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  deleteConversation,
  getConversation,
  money,
  sendChat,
  type ChatAnswer,
  type Comparison,
  type Filters,
  type Product,
} from "../api";
import { Button } from "./Button";

type Message = {
  role: "user" | "assistant";
  content: string;
  answer?: ChatAnswer;
};
type Props = {
  open: boolean;
  prompt: { id: number; text: string } | null;
  onClose: () => void;
  onProduct: (product: Product) => void;
  onComparison: (comparison: Comparison) => void;
};

export function ChatPanel({
  open,
  prompt,
  onClose,
  onProduct,
  onComparison,
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [ready, setReady] = useState(false);
  const [filters, setFilters] = useState<Filters>({});
  const scroll = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const lastPrompt = useRef(0);
  const busy = useRef(false);

  useEffect(() => {
    const id = localStorage.getItem("seek.session");
    if (!id) {
      setReady(true);
      return;
    }
    let cancelled = false;
    getConversation(id)
      .then((conversation) => {
        if (cancelled) return;
        setSessionId(conversation.session_id);
        setFilters(conversation.state.filters);
        setMessages(
          conversation.messages.map((item) => ({
            role: item.role,
            content: item.content,
            answer: item.role === "assistant" ? item.payload : undefined,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) localStorage.removeItem("seek.session");
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [messages, pending, open]);
  useEffect(() => {
    if (open) textarea.current?.focus();
  }, [open]);
  useEffect(() => {
    if (ready && prompt && lastPrompt.current !== prompt.id && !busy.current) {
      lastPrompt.current = prompt.id;
      void submitMessage(prompt.text);
    }
  }, [ready, prompt]);

  async function submitMessage(text: string) {
    const content = text.trim();
    if (!content || busy.current || !ready) return;
    busy.current = true;
    setPending(true);
    setInput("");
    setMessages((previous) => [...previous, { role: "user", content }]);
    try {
      const answer = await sendChat(content, sessionId);
      setSessionId(answer.session_id);
      localStorage.setItem("seek.session", answer.session_id);
      setFilters(answer.filters);
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: answer.message, answer },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            error instanceof Error
              ? error.message
              : "暂时连接不上服务，请稍后重试。",
        },
      ]);
    } finally {
      busy.current = false;
      setPending(false);
      textarea.current?.focus();
    }
  }

  async function newConversation() {
    if (pending) return;
    if (sessionId) {
      try {
        await deleteConversation(sessionId);
      } catch {
        return;
      }
    }
    localStorage.removeItem("seek.session");
    setSessionId(null);
    setMessages([]);
    setFilters({});
    setInput("");
  }

  const chips = [
    filters.category,
    filters.color,
    filters.max_price != null ? `¥${money(filters.max_price)} 内` : null,
    ...(filters.exclude_tags ?? []).map((tag) => `不要${tag}`),
  ].filter(Boolean);

  return (
    <aside
      className={`chat-panel ${open ? "is-open" : ""}`}
      aria-label="AI 导购助手"
      role="dialog"
      hidden={!open}
    >
      <header className="chat-header">
        <div className="assistant-avatar">
          <Sparkles size={20} />
        </div>
        <div>
          <h2>
            寻物 AI 助手<span>BETA</span>
          </h2>
          <p>
            <span className="status-dot" />
            懂你的每一个小要求
          </p>
        </div>
        <div className="chat-header-actions">
          <button
            aria-label="开始新对话"
            title="开始新对话"
            disabled={pending}
            onClick={() => void newConversation()}
          >
            <Plus size={19} />
          </button>
          <button aria-label="关闭导购助手" onClick={onClose}>
            <X size={19} />
          </button>
        </div>
      </header>
      <div className="chat-scroll" ref={scroll}>
        {messages.length === 0 && (
          <div className="chat-welcome">
            <span className="welcome-orbit">
              <Sparkles size={31} strokeWidth={1.4} />
            </span>
            <span className="eyebrow">YOUR PERSONAL FINDER</span>
            <h3>
              好物很多，
              <br />
              适合你的才刚刚好。
            </h3>
            <p>
              告诉我你的预算、场景和偏好，
              <br />
              剩下的，一起慢慢挑。
            </p>
            <div className="chat-suggestions">
              {[
                "500 元以内的白色通勤鞋",
                "想找一双轻量徒步鞋",
                "推荐一个能装电脑的通勤包",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  disabled={!ready}
                  onClick={() => void submitMessage(suggestion)}
                >
                  <MessageCircle size={15} />
                  <span>{suggestion}</span>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
            <div className="chat-welcome-foot">
              <ArrowDownLeft size={14} />
              也可以从任何一件喜欢的商品聊起
            </div>
          </div>
        )}
        <div className="chat-messages" aria-live="polite">
          {messages.map((message, index) => (
            <div key={index} className={`chat-message ${message.role}`}>
              {message.role === "assistant" && (
                <div className="message-label">
                  <Sparkles size={12} /> SEEK ASSISTANT
                </div>
              )}
              <div className="message-text">{message.content}</div>
              {message.answer?.degraded && (
                <p className="chat-notice">
                  智能服务暂不可用 · 已根据商品记录提供结果
                </p>
              )}
              {message.answer?.products &&
                message.answer.products.length > 0 && (
                  <div className="chat-products">
                    {message.answer.products.slice(0, 4).map((product) => (
                      <button
                        key={product.id}
                        className="chat-product"
                        onClick={() => onProduct(product)}
                      >
                        <img src={product.image} alt={product.name} />
                        <span>
                          <small>{product.brand}</small>
                          <strong>{product.name}</strong>
                          <b>¥{money(product.price)}</b>
                        </span>
                        <ArrowUpRight size={15} />
                      </button>
                    ))}
                  </div>
                )}
              {message.answer?.comparison && (
                <Button
                  variant="secondary"
                  size="small"
                  className="chat-compare"
                  onClick={() => onComparison(message.answer!.comparison!)}
                >
                  <Scale size={15} />
                  查看完整商品对比
                  <ArrowUpRight size={14} />
                </Button>
              )}
            </div>
          ))}
        </div>
        {pending && (
          <div className="chat-pending" role="status">
            <span className="thinking-dots">
              <i />
              <i />
              <i />
            </span>
            正在查找适合你的好物…
          </div>
        )}
      </div>
      <div className="chat-input-area">
        {chips.length > 0 && (
          <div className="chat-filter-chips">
            <span>已记住</span>
            {chips.map((chip) => (
              <span key={chip}>{chip}</span>
            ))}
          </div>
        )}
        <form
          className="chat-input"
          onSubmit={(event) => {
            event.preventDefault();
            void submitMessage(input);
          }}
        >
          <textarea
            ref={textarea}
            value={input}
            maxLength={2000}
            rows={2}
            disabled={pending || !ready}
            placeholder="说说你想找什么…"
            aria-label="输入购物需求"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !event.nativeEvent.isComposing
              ) {
                event.preventDefault();
                void submitMessage(input);
              }
            }}
          />
          <button
            type="submit"
            disabled={pending || !ready || !input.trim()}
            aria-label="发送购物需求"
          >
            {pending ? (
              <LoaderCircle size={18} className="spin" />
            ) : (
              <ArrowUp size={19} />
            )}
          </button>
        </form>
        <p className="chat-footnote">AI 辅助选购，商品与规格均为模拟信息</p>
      </div>
    </aside>
  );
}

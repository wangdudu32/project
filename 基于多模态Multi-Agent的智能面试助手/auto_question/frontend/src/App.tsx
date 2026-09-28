import { useEffect, useState } from 'react'
import { ArrowUpRight, BookOpen, CheckCircle2, FileText, History, LoaderCircle, Plus, Sparkles } from 'lucide-react'
import { api, errorMessage } from './api'
import type { Difficulty, Evaluation, Health, HistoryItem, Interview, Language, UploadedDocument } from './api'
import './App.css'

const difficulties = { easy: '基础', medium: '进阶', hard: '挑战' }
const researchUrl = import.meta.env.VITE_RESEARCH_URL || 'http://localhost:5183'
const formatDate = (value: string) => new Date(value).toLocaleString('zh-CN', { hour12: false })

function Scores({ value }: { value: Pick<Evaluation, 'score' | 'correctness' | 'depth' | 'clarity'> }) {
  return <div className="scores">
    {([['总分', value.score], ['准确性', value.correctness], ['技术深度', value.depth], ['表达清晰度', value.clarity]] as const).map(([label, score]) =>
      <div key={label}><strong>{score}<small> / 100</small></strong><span>{label}</span></div>)}
  </div>
}

function App() {
  const [view, setView] = useState<'new' | 'history' | 'interview'>('new')
  const [health, setHealth] = useState<Health | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [interview, setInterview] = useState<Interview | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [document, setDocument] = useState<UploadedDocument | null>(null)
  const [count, setCount] = useState(3)
  const [difficulty, setDifficulty] = useState<Difficulty>('medium')
  const [language, setLanguage] = useState<Language>('zh')
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [healthResult, historyResult] = await Promise.all([
          api.get<Health>('/health'), api.get<HistoryItem[]>('/interviews'),
        ])
        if (!cancelled) {
          setHealth(healthResult.data)
          setHistory(historyResult.data)
        }
      } catch (e) {
        if (!cancelled) setError(errorMessage(e))
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])

  async function refreshHistory() {
    const res = await api.get<HistoryItem[]>('/interviews')
    setHistory(res.data)
  }

  async function perform(label: string, action: () => Promise<void>) {
    if (busy) return
    setBusy(label)
    setError('')
    try {
      await action()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy('')
    }
  }

  function newInterview() {
    setView('new')
    setInterview(null)
    setFile(null)
    setDocument(null)
    setDrafts({})
    setError('')
  }

  async function generate() {
    if (!file) return
    await perform('正在解析资料、生成并审核题目，可能需要几分钟…', async () => {
      let uploaded = document
      if (!uploaded) {
        const data = new FormData()
        data.append('file', file)
        uploaded = (await api.post<UploadedDocument>('/upload', data)).data
        setDocument(uploaded)
      }
      const res = await api.post<Interview>('/generate', {
        document_id: uploaded.document_id, num_questions: count, difficulty, language,
      })
      setInterview(res.data)
      setDrafts({})
      setView('interview')
      await refreshHistory()
    })
  }

  async function openInterview(id: string) {
    await perform('正在读取面试记录…', async () => {
      const res = await api.get<Interview>('/interviews/' + id)
      setInterview(res.data)
      setDrafts({})
      setView('interview')
    })
  }

  async function updateInterview(path: string, label: string, data?: object) {
    if (!interview) return
    await perform(label, async () => {
      const res = await api.post<Interview>('/interviews/' + interview.id + path, data)
      setInterview(res.data)
      await refreshHistory()
    })
  }

  function downloadReport() {
    if (!interview?.report) return
    const report = interview.report
    const lines = [
      '# 面试总结', '', '资料：' + interview.filename, '时间：' + formatDate(report.completed_at),
      '总分：' + report.score + '/100',
      '准确性：' + report.correctness + '；技术深度：' + report.depth + '；表达清晰度：' + report.clarity,
      '', '## 优点', ...report.strengths.map(s => '- ' + s),
      '', '## 改进建议', ...report.improvements.map(s => '- ' + s),
      '', 'AI 评分仅供练习参考。', '',
      ...interview.questions.flatMap((q, i) => [
        '## ' + (i + 1) + '. ' + q.question, '',
        '我的回答：' + q.user_answer, '', '反馈：' + q.evaluation?.feedback,
        '', '参考答案：' + q.answer, '', '知识点：' + q.analysis, '',
      ]),
    ]
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' }))
    const anchor = window.document.createElement('a')
    anchor.href = url
    anchor.download = '面试总结-' + interview.id.slice(0, 8) + '.md'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const answered = interview?.questions.filter(q => q.evaluation).length || 0
  const allAnswered = !!interview && answered === interview.questions.length

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="智能面试助手首页"><span className="brand-icon"><Sparkles size={23} /></span><div><strong>智能面试助手</strong><small>把知识变成面试能力</small></div></a>
      <button className="primary new-button" disabled={!!busy} onClick={newInterview}><Plus size={18} />新建面试</button>
      <nav aria-label="主导航">
        <button className={view === 'new' ? 'nav-item selected' : 'nav-item'} disabled={!!busy} onClick={() => setView('new')}><BookOpen size={18} />资料出题</button>
        <button className={view === 'history' ? 'nav-item selected' : 'nav-item'} disabled={!!busy} onClick={() => { setView('history'); void perform('正在读取历史记录…', refreshHistory) }}><History size={18} />面试记录 <span className="count">{history.length}</span></button>
        {interview && <button className={view === 'interview' ? 'nav-item selected' : 'nav-item'} disabled={!!busy} onClick={() => setView('interview')}><FileText size={18} />当前面试</button>}
        <a className="nav-item" href={researchUrl} target="_blank" rel="noreferrer"><ArrowUpRight size={18} />行业研究助手</a>
      </nav>
      <div className="sidebar-note"><span className={'status-dot ' + (health?.model_configured ? 'ready' : '')} />{health ? (health.model_configured ? '模型配置已就绪' : '等待配置模型') : '正在连接后端'}<p>资料与面试记录保存在当前服务中。</p></div>
    </aside>

    <main className="main-content">
      <header className="topbar"><span>学习 / {view === 'history' ? '面试记录' : view === 'interview' ? '模拟面试' : '资料出题'}</span><span className="tag">文字模拟面试</span></header>
      {error && <div className="alert error" role="alert">{error}<button className="text-button" onClick={() => setError('')}>关闭</button></div>}
      {busy && <div className="alert loading" role="status"><LoaderCircle size={18} className="spin" />{busy}</div>}

      {view === 'new' && <section className="workspace">
        <div className="eyebrow">准备好，开始下一次练习</div>
        <h1>从一份资料，开始一场面试</h1>
        <p className="intro">上传论文或学习资料，让 AI 出题、审核，并根据你的回答给出反馈和追问。</p>
        {health && !health.model_configured && <div className="alert warning">模型尚未配置。请按 README 设置模型连接，重启后端后刷新页面。</div>}
        <div className="panel">
          <h2><span className="step-number">1</span>上传学习资料</h2>
          <label className="upload-zone">
            <span className="upload-icon"><FileText size={30} /></span>
            <strong>{file ? file.name : '选择一份 PDF 文件'}</strong>
            <span>{file ? (file.size / 1024 / 1024).toFixed(2) + ' MB · 点击可重新选择' : '支持论文、技术文档、复习笔记'}</span>
            <small>最大 20 MB、200 页；均匀抽取最多 10 页作为出题材料</small>
            <input aria-label="选择 PDF 文件" type="file" accept=".pdf,application/pdf" disabled={!!busy} onChange={e => {
              const selected = e.target.files?.[0] || null
              setFile(null); setDocument(null); setError('')
              if (selected && selected.size > 20 * 1024 * 1024) { setError('文件不能超过 20 MB。'); return }
              setFile(selected)
            }} />
          </label>
          {document && <p className="success-text"><CheckCircle2 size={16} />资料已上传，共 {document.page_count} 页</p>}
          <h2><span className="step-number">2</span>设置面试内容</h2>
          <div className="settings-grid">
            <label>题目数量<select value={count} disabled={!!busy} onChange={e => setCount(Number(e.target.value))}>{Array.from({ length: 10 }, (_, i) => i + 1).map(n => <option key={n} value={n}>{n} 道题</option>)}</select></label>
            <label>题目难度<select value={difficulty} disabled={!!busy} onChange={e => setDifficulty(e.target.value as Difficulty)}>{Object.entries(difficulties).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
            <label>面试语言<select value={language} disabled={!!busy} onChange={e => setLanguage(e.target.value as Language)}><option value="zh">中文</option><option value="en">English</option></select></label>
          </div>
          <div className="panel-footer"><p>提交作答后，展示参考答案和评分反馈。</p><button className="primary" disabled={!file || !!busy || !health?.model_configured} onClick={() => void generate()}><Sparkles size={17} />生成面试题</button></div>
        </div>
        <div className="feature-grid">{[['理解资料', '结合文档中的文字、图表生成问题。'], ['审核题目', '自动检查题目和答案，必要时修订。'], ['作答复盘', '查看评分、补充追问，保存练习记录。']].map(([title, description], i) =>
          <div key={title}><span>0{i + 1}</span><h3>{title}</h3><p>{description}</p></div>)}</div>
      </section>}

      {view === 'history' && <section className="workspace">
        <div className="eyebrow">每次练习，都有记录</div><h1>面试记录</h1><p className="intro">继续未完成的面试，或查看已经完成的总结。这里显示最近 100 条记录。</p>
        {!history.length ? <div className="panel empty">还没有面试记录，上传一份资料开始练习吧。</div> : <div className="history-list">{history.map(item =>
          <button key={item.id} className="history-card" disabled={!!busy} onClick={() => void openInterview(item.id)}>
            <FileText size={23} /><div><strong>{item.filename}</strong><small>{formatDate(item.created_at)} · {difficulties[item.difficulty]} · 已答 {item.answered_count}/{item.question_count} 题</small></div>
            <span className="tag">{item.status === 'completed' ? item.score + ' 分' : '继续作答'}</span>
          </button>)}</div>}
      </section>}

      {view === 'interview' && interview && <section className="workspace interview-workspace">
        <div className="eyebrow">{interview.status === 'completed' ? '练习已完成' : '专注思考，清楚表达'}</div>
        <h1>{interview.status === 'completed' ? '面试总结' : '模拟面试'}</h1>
        <p className="intro filename">{interview.filename} · {difficulties[interview.difficulty]} · 已答 {answered}/{interview.questions.length} 题</p>
        <p className="muted">出题材料页码：{interview.source_pages.join('、')}。AI 评分用于练习参考。</p>
        {interview.questions.some(q => q.status !== 'verified') && <div className="alert warning">部分题目未通过自动审核，已在题目旁标注。请结合原文核对参考答案。</div>}
        {interview.report && <div className="panel report-panel">
          <div className="section-title"><h2>本次表现</h2><button className="secondary" onClick={downloadReport}>下载总结</button></div>
          <Scores value={interview.report} /><p className="muted">总分按准确性 50%、技术深度 30%、表达清晰度 20% 加权；各题（含追问）取平均。</p>
          <div className="feedback-grid"><div><h3>表现较好的地方</h3><ul>{interview.report.strengths.map(s => <li key={s}>{s}</li>)}</ul></div><div><h3>接下来可以练习</h3><ul>{interview.report.improvements.map(s => <li key={s}>{s}</li>)}</ul></div></div>
        </div>}
        {interview.questions.map((q, i) => <article className="panel question-card" key={q.id}>
          <div className="question-meta"><span className="tag">{q.parent_id ? '追问' : '问题'} {i + 1}</span><span>来源：第 {q.page} 页</span><span className={q.status === 'verified' ? 'verified' : 'unverified'}>{q.status === 'verified' ? '审核通过' : '待人工核对'}</span></div>
          <h2>{q.question}</h2>
          {q.evaluation ? <>
            <div className="submitted-answer"><h3>我的回答</h3><p>{q.user_answer}</p></div>
            <Scores value={q.evaluation} /><p className="feedback-text">{q.evaluation.feedback}</p>
            <div className="feedback-grid"><div><h3>优点</h3><ul>{q.evaluation.strengths.map(s => <li key={s}>{s}</li>)}</ul></div><div><h3>改进建议</h3><ul>{q.evaluation.improvements.map(s => <li key={s}>{s}</li>)}</ul></div></div>
            <details><summary>参考答案与知识点</summary><h3>参考答案</h3><p>{q.answer}</p><h3>考查内容</h3><p>{q.analysis}</p>{q.status !== 'verified' && <p className="unverified">审核意见：{q.feedback}</p>}</details>
            {interview.status === 'active' && !q.parent_id && !interview.questions.some(item => item.parent_id === q.id) &&
              <button className="secondary followup-button" disabled={!!busy} onClick={() => void updateInterview('/questions/' + q.id + '/followup', '正在根据你的回答生成追问…')}>针对这道题继续追问</button>}
          </> : <form onSubmit={e => { e.preventDefault(); void updateInterview('/questions/' + q.id + '/answer', '正在评估回答，请稍候…', { answer: drafts[q.id]?.trim() }) }}>
            <label className="answer-label" htmlFor={'answer-' + q.id}>你的回答</label>
            <textarea id={'answer-' + q.id} placeholder="试着说明你的理解、推理过程和具体例子…" value={drafts[q.id] || ''} maxLength={12000} disabled={!!busy} onChange={e => setDrafts({ ...drafts, [q.id]: e.target.value })} />
            <div className="answer-footer"><span>{(drafts[q.id] || '').length}/12000 · 提交后不可修改</span><button className="primary" disabled={!!busy || !drafts[q.id]?.trim()}>提交回答</button></div>
          </form>}
        </article>)}
        {interview.status === 'active' && <div className="finish-bar"><p>{allAnswered ? '已完成所有题目，可以生成总结，也可以选择追问。' : '完成所有题目后，即可查看本次面试总结。'}</p><button className="primary" disabled={!!busy || !allAnswered} onClick={() => void updateInterview('/finish', '正在整理面试总结…')}>完成面试并查看总结</button></div>}
      </section>}
    </main>
  </div>
}

export default App

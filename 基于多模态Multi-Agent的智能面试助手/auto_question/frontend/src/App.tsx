import { useState, useRef } from 'react'
import axios from 'axios'
import { 
  Upload, FileText, CheckCircle, AlertCircle, Loader2, 
  BrainCircuit, Sparkles, ShieldCheck, FileSearch, ArrowRight, Zap,
  Layout, History, Settings, MoreHorizontal, Plus, ChevronRight
} from 'lucide-react'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { motion, AnimatePresence } from 'framer-motion'

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs))
}

const SidebarItem = ({ icon: Icon, label, active = false }: { icon: any, label: string, active?: boolean }) => (
  <div className={cn(
    "flex items-center space-x-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all text-sm font-medium group",
    active 
      ? "bg-gradient-to-r from-indigo-50 to-purple-50 text-indigo-700 shadow-sm" 
      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
  )}>
    <Icon className={cn("w-4 h-4 transition-transform group-hover:scale-110", active ? "text-indigo-600" : "text-gray-400")} />
    <span>{label}</span>
    {active && <ChevronRight className="w-3 h-3 ml-auto text-indigo-400" />}
  </div>
)

const StepIndicator = ({ 
  active, 
  completed, 
  icon: Icon, 
  label, 
}: { 
  active: boolean
  completed: boolean
  icon: any
  label: string
}) => {
  return (
    <div className="flex items-center space-x-2">
      <motion.div 
        animate={{ 
          scale: active ? 1.1 : 1,
          rotate: active ? 360 : 0
        }}
        transition={{ duration: 0.5 }}
        className={cn(
          "w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 border-2",
          active 
            ? "bg-gradient-to-br from-indigo-500 to-purple-600 border-indigo-300 shadow-lg shadow-indigo-200" 
            : completed 
              ? "bg-gradient-to-br from-emerald-500 to-teal-600 border-emerald-300" 
              : "bg-white border-gray-200"
        )}
      >
        <Icon className={cn("w-3.5 h-3.5", active || completed ? "text-white" : "text-gray-300")} />
      </motion.div>
      <span className={cn(
        "text-xs font-semibold transition-colors duration-300",
        active ? "text-indigo-600" : completed ? "text-emerald-600" : "text-gray-400"
      )}>
        {label}
      </span>
    </div>
  )
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [questions, setQuestions] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [filePath, setFilePath] = useState<string | null>(null)
  const [step, setStep] = useState<number>(0) 

  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
      setQuestions([])
      setStep(0)
    }
  }

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await axios.post('/api/upload', formData)
      setFilePath(res.data.path)
    } catch (err) {
      setError('Upload failed, please try again')
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  const handleGenerate = async () => {
    if (!filePath) return
    setGenerating(true)
    setQuestions([])
    setError(null)
    setStep(1) 

    const timer1 = setTimeout(() => setStep(2), 2500) 
    const timer2 = setTimeout(() => setStep(3), 5000) 

    try {
      const res = await axios.post('/api/generate', {
        pdf_path: filePath,
        num_questions: 3
      })
      
      clearTimeout(timer1)
      clearTimeout(timer2)
      setStep(4) 
      setQuestions(res.data.questions)
    } catch (err) {
      setError('Generation failed, please try again')
      console.error(err)
      setStep(0)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-gray-50 to-zinc-50 text-gray-900 font-sans overflow-hidden">
      
      <div className="w-[280px] bg-white/80 backdrop-blur-xl border-r border-gray-200 flex-col hidden md:flex shadow-sm">
        <div className="p-5">
          <div className="flex items-center space-x-3 mb-8 px-2">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-600 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-200">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">CodeBear</h1>
              <p className="text-[10px] text-gray-400 font-medium">AI Question Generator</p>
            </div>
          </div>

          <button 
            onClick={() => {
              setFile(null); 
              setQuestions([]);
              setStep(0);
              setFilePath(null);
            }}
            className="w-full flex items-center justify-center space-x-2 px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-2xl shadow-lg shadow-indigo-200 hover:shadow-xl hover:shadow-indigo-300 transition-all hover:scale-[1.02] active:scale-[0.98] text-sm font-semibold mb-6"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>

          <div className="space-y-1.5">
            <SidebarItem icon={Layout} label="Dashboard" active />
            <SidebarItem icon={History} label="History" />
            <SidebarItem icon={FileSearch} label="Research" />
            <SidebarItem icon={Settings} label="Settings" />
          </div>
        </div>
        
        <div className="mt-auto p-5 border-t border-gray-200">
           <div className="flex items-center space-x-3 px-3 py-3 cursor-pointer hover:bg-gray-50 rounded-2xl transition-all group">
             <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shadow-md">
               FX
             </div>
             <div className="flex-1">
               <p className="text-sm font-semibold text-gray-900">User Account</p>
               <p className="text-xs text-gray-500">Pro Plan</p>
             </div>
             <MoreHorizontal className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
           </div>
        </div>
      </div>

      <div className="flex-1 flex flex-col relative min-w-0">
        
        <header className="h-16 flex items-center justify-between px-8 z-10 bg-white/60 backdrop-blur-xl border-b border-gray-200 sticky top-0">
          <div className="flex items-center space-x-3">
             <div className="flex items-center space-x-2 px-3 py-1.5 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-full border border-indigo-200">
               <div className="w-2 h-2 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 animate-pulse" />
               <span className="text-xs font-semibold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">Qwen 2.5 VL</span>
             </div>
             <span className="text-sm text-gray-400">/</span>
             <span className="text-sm font-medium text-gray-600">Question Generation</span>
          </div>
          <div className="flex items-center space-x-4">
            <StepIndicator active={step === 1} completed={step > 1} icon={BrainCircuit} label="Generate" />
            <div className="w-8 h-[2px] bg-gradient-to-r from-gray-300 to-transparent" />
            <StepIndicator active={step === 2} completed={step > 2} icon={ShieldCheck} label="Verify" />
            <div className="w-8 h-[2px] bg-gradient-to-r from-gray-300 to-transparent" />
            <StepIndicator active={step === 3} completed={step > 3} icon={FileSearch} label="Refine" />
          </div>
        </header>

        <main className="flex-1 overflow-y-auto scroll-smooth">
          <div className="max-w-4xl mx-auto px-8 py-12 pb-32 min-h-full flex flex-col">
            
            <AnimatePresence>
              {questions.length === 0 && !generating && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center -mt-16"
                >
                  <motion.div 
                    animate={{ 
                      scale: [1, 1.05, 1],
                      rotate: [0, 5, -5, 0]
                    }}
                    transition={{ 
                      duration: 3,
                      repeat: Infinity,
                      repeatType: "reverse"
                    }}
                    className="w-20 h-20 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-3xl flex items-center justify-center mb-8 shadow-2xl shadow-indigo-300"
                  >
                    <Sparkles className="w-10 h-10 text-white" />
                  </motion.div>
                  
                  <h2 className="text-3xl font-bold bg-gradient-to-r from-gray-900 via-indigo-900 to-purple-900 bg-clip-text text-transparent mb-3">
                    CodeBear LLM Question Generation
                  </h2>
                  <p className="text-gray-500 mb-12 text-center max-w-md">
                    Upload a PDF document and let our multi-agent AI system generate high-quality interview questions
                  </p>

                  <div className="w-full max-w-2xl relative">
                    {!file ? (
                       <motion.div 
                         whileHover={{ scale: 1.01 }}
                         whileTap={{ scale: 0.99 }}
                         onClick={() => fileInputRef.current?.click()}
                         className="w-full min-h-[140px] p-6 rounded-3xl border-2 border-dashed border-gray-300 bg-white hover:border-indigo-400 hover:bg-gradient-to-br hover:from-indigo-50/50 hover:to-purple-50/50 transition-all cursor-pointer flex flex-col justify-between group shadow-sm hover:shadow-xl"
                       >
                         <div className="flex items-center space-x-3 text-gray-400 group-hover:text-indigo-500 transition-colors">
                           <Upload className="w-5 h-5" />
                           <span className="text-lg font-medium">Upload PDF to start generating...</span>
                         </div>
                         <div className="flex items-center justify-between mt-6">
                            <div className="flex items-center space-x-2 text-xs text-gray-400 bg-gray-50 px-3 py-2 rounded-2xl group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
                              <FileText className="w-3.5 h-3.5" />
                              <span>Drag & drop supported</span>
                            </div>
                            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-200 group-hover:from-indigo-500 group-hover:to-purple-600 flex items-center justify-center transition-all shadow-sm group-hover:shadow-lg">
                              <ArrowRight className="w-5 h-5 text-gray-400 group-hover:text-white transition-colors" />
                            </div>
                         </div>
                       </motion.div>
                    ) : (
                      <motion.div 
                        initial={{ scale: 0.95, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        className="w-full p-5 rounded-3xl border-2 border-gray-300 bg-white shadow-xl flex items-center justify-between"
                      >
                         <div className="flex items-center space-x-4">
                           <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-red-50 to-orange-50 border-2 border-red-200 flex items-center justify-center shadow-sm">
                              <FileText className="w-7 h-7 text-red-500" />
                           </div>
                           <div>
                              <p className="text-sm font-semibold text-gray-900">{file.name}</p>
                              <p className="text-xs text-gray-500 mt-0.5">{(file.size / 1024 / 1024).toFixed(2)} MB · PDF Document</p>
                           </div>
                         </div>
                         <div className="flex items-center space-x-3">
                           {!filePath ? (
                             <button 
                               onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                               disabled={uploading}
                               className="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-2xl text-sm font-semibold hover:shadow-lg hover:shadow-indigo-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                             >
                               {uploading ? (
                                 <span className="flex items-center space-x-2">
                                   <Loader2 className="w-4 h-4 animate-spin" />
                                   <span>Uploading...</span>
                                 </span>
                               ) : 'Confirm Upload'}
                             </button>
                           ) : (
                             <button 
                               onClick={(e) => { e.stopPropagation(); handleGenerate(); }}
                               className="px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-2xl text-sm font-semibold hover:shadow-lg hover:shadow-indigo-300 transition-all flex items-center space-x-2"
                             >
                               <Zap className="w-4 h-4" />
                               <span>Start Generation</span>
                             </button>
                           )}
                           <button 
                             onClick={(e) => { e.stopPropagation(); setFile(null); setFilePath(null); }}
                             className="p-2.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-2xl transition-colors"
                           >
                             ✕
                           </button>
                         </div>
                      </motion.div>
                    )}
                    <input ref={fileInputRef} type="file" className="hidden" accept=".pdf" onChange={handleFileChange} />
                  </div>
                  
                  {error && (
                    <motion.p 
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-6 text-red-600 text-sm bg-red-50 px-4 py-2 rounded-full border-2 border-red-200"
                    >
                      {error}
                    </motion.p>
                  )}

                  <div className="flex items-center space-x-3 mt-10">
                    {["Deep Learning", "System Design", "Python Basics"].map((tag) => (
                      <span key={tag} className="px-4 py-2 rounded-full bg-white border-2 border-gray-300 text-xs font-medium text-gray-600 hover:border-indigo-400 hover:bg-indigo-50 hover:text-indigo-600 cursor-pointer transition-all shadow-sm hover:shadow-md">
                        {tag}
                      </span>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {generating && step < 4 && (
               <motion.div 
                 initial={{ opacity: 0 }}
                 animate={{ opacity: 1 }}
                 className="flex flex-col items-center justify-center py-24 space-y-8"
               >
                  <div className="relative">
                    <motion.div 
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                      className="w-16 h-16 rounded-full border-4 border-gray-200 border-t-indigo-600"
                    />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Sparkles className="w-6 h-6 text-indigo-600 animate-pulse" />
                    </div>
                  </div>
                  <div className="text-center space-y-2">
                    <h3 className="text-lg font-semibold text-gray-900">
                      {step === 1 && "🧠 AI is thinking..."}
                      {step === 2 && "🔍 Verifying accuracy..."}
                      {step === 3 && "✨ Refining quality..."}
                    </h3>
                    <p className="text-sm text-gray-500 max-w-md">
                      Multi-agent system is collaborating to analyze document content and extract key knowledge
                    </p>
                  </div>
               </motion.div>
            )}

            <AnimatePresence>
               {questions.length > 0 && step === 4 && (
                 <motion.div 
                   initial={{ opacity: 0 }} 
                   animate={{ opacity: 1 }}
                   className="space-y-10"
                 >
                    {questions.map((q, idx) => (
                       <motion.div 
                         key={idx}
                         initial={{ opacity: 0, y: 30 }}
                         animate={{ opacity: 1, y: 0 }}
                         transition={{ delay: idx * 0.15, type: "spring" }}
                         className="space-y-5"
                       >
                          <div className="flex space-x-4">
                             <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-200 flex-shrink-0 flex items-center justify-center shadow-sm border-2 border-gray-300">
                                <span className="font-bold text-sm text-gray-700">{idx + 1}</span>
                             </div>
                             <div className="flex-1 space-y-3">
                                <h3 className="text-xl font-semibold text-gray-900 leading-relaxed">
                                  {q.question}
                                </h3>
                                <div className="flex space-x-2">
                                   <span className={cn(
                                     "text-[10px] px-3 py-1 rounded-full font-bold uppercase tracking-wider shadow-sm border-2",
                                     q.difficulty === 'hard' 
                                       ? "bg-gradient-to-r from-red-500 to-orange-500 text-white border-red-600" 
                                       : "bg-gradient-to-r from-emerald-500 to-teal-500 text-white border-emerald-600"
                                   )}>{q.difficulty || 'Medium'}</span>
                                </div>
                             </div>
                          </div>

                          {/* Answer */}
                          <div className="flex space-x-4">
                             <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-600 to-purple-600 flex-shrink-0 flex items-center justify-center shadow-lg shadow-indigo-200 border-2 border-indigo-700">
                                <Sparkles className="w-5 h-5 text-white" />
                             </div>
                             <div className="flex-1 space-y-5">
                                <div className="space-y-3">
                                   {q.options ? (
                                      q.options.map((opt: string, i: number) => (
                                         <motion.div 
                                           key={i}
                                           whileHover={{ scale: 1.01, x: 4 }}
                                           className={cn(
                                            "p-4 rounded-2xl border-2 text-sm transition-all cursor-pointer",
                                            opt.startsWith(q.answer) 
                                              ? "bg-gradient-to-r from-indigo-50 to-purple-50 border-indigo-400 text-gray-900 font-semibold shadow-md" 
                                              : "bg-white border-gray-300 text-gray-600 hover:border-gray-400 hover:shadow-sm"
                                         )}>
                                            <div className="flex items-center space-x-3">
                                              {opt.startsWith(q.answer) && <CheckCircle className="w-4 h-4 text-indigo-600" />}
                                              <span>{opt}</span>
                                            </div>
                                         </motion.div>
                                      ))
                                   ) : (
                                      <div className="prose prose-sm text-gray-700 max-w-none bg-white p-5 rounded-2xl border-2 border-gray-300 shadow-sm">
                                         {q.answer}
                                      </div>
                                   )}
                                </div>

                                <div className="bg-gradient-to-br from-gray-50 to-indigo-50/30 rounded-2xl p-5 border-2 border-gray-300 shadow-sm">
                                   <div className="flex items-center space-x-2 text-xs font-bold text-indigo-600 uppercase tracking-wider mb-3">
                                     <BrainCircuit className="w-4 h-4" />
                                     <span>AI Analysis</span>
                                   </div>
                                   <p className="text-sm text-gray-700 leading-relaxed">{q.analysis}</p>
                                </div>

                                <div className="flex items-center space-x-3">
                                   <button className="px-3 py-1.5 rounded-2xl bg-white border-2 border-gray-300 text-xs font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-400 transition-all flex items-center space-x-1.5">
                                     <span>📋</span>
                                     <span>Copy</span>
                                   </button>
                                   <button className="px-3 py-1.5 rounded-2xl bg-white border-2 border-gray-300 text-xs font-medium text-gray-600 hover:bg-gray-50 hover:border-gray-400 transition-all flex items-center space-x-1.5">
                                     <span>🔄</span>
                                     <span>Regenerate</span>
                                   </button>
                                </div>
                             </div>
                          </div>
                       </motion.div>
                    ))}
                    
                    <div className="pt-10 flex justify-center">
                       <button 
                         onClick={handleGenerate} 
                         className="px-6 py-3 bg-white border-2 border-gray-300 shadow-md rounded-2xl text-sm font-semibold text-gray-700 hover:bg-gray-50 hover:border-gray-400 hover:shadow-lg transition-all flex items-center space-x-2"
                       >
                         <Loader2 className="w-4 h-4" />
                         <span>Regenerate All Questions</span>
                       </button>
                    </div>
                 </motion.div>
               )}
            </AnimatePresence>

          </div>
        </main>
      </div>
    </div>
  )
}

export default App
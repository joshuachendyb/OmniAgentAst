import { Agentation } from 'agentation'

function App() {
  const handleAnnotation = (annotation) => {
    console.log('Agentation 标注:', annotation)
    // 发送给 AI Agent 或保存到本地
  }

  return (
    <>
      {/* 你的应用内容 */}
      <div className="app">
        <header className="header">
          <h1>我的 React 应用</h1>
        </header>
        
        <main className="main-content">
          <button className="btn-primary">主要按钮</button>
          <button className="btn-secondary">次要按钮</button>
          
          <div className="card">
            <h2>卡片标题</h2>
            <p>卡片内容</p>
          </div>
        </main>
      </div>

      {/* Agentation 工具栏 - 仅开发环境显示 */}
      {process.env.NODE_ENV === 'development' && (
        <Agentation
          onAnnotationAdd={handleAnnotation}
          copyToClipboard={true}
        />
      )}
    </>
  )
}

export default App

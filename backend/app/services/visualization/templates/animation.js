const operations = {{ operations_json }};
let currentIndex = 0;
let isPlaying = false;
let animationInterval = null;

function renderOperations() {
    const container = document.getElementById('operations');
    container.innerHTML = '';
    
    operations.forEach((op, index) => {
        const div = document.createElement('div');
        div.className = `operation ${op.status}`;
        div.id = `op-${index}`;
        
        const typeMap = {
            'create': '📄 创建',
            'delete': '🗑️ 删除',
            'move': '📦 移动',
            'copy': '📋 复制',
            'rename': '✏️ 重命名',
            'modify': '✏️ 修改'
        };
        
        let pathHtml = '';
        if (op.source && op.destination) {
            pathHtml = `<span class="operation-path">${op.source}</span>
                       <span class="operation-arrow">→</span>
                       <span class="operation-path">${op.destination}</span>`;
        } else if (op.source) {
            pathHtml = `<span class="operation-path">${op.source}</span>`;
        } else if (op.destination) {
            pathHtml = `<span class="operation-path">${op.destination}</span>`;
        }
        
        div.innerHTML = `
            <div class="operation-type">${typeMap[op.type] || op.type}</div>
            <div>${pathHtml}</div>
        `;
        
        container.appendChild(div);
    });
}

function updateProgress() {
    const progress = (currentIndex / operations.length) * 100;
    document.getElementById('progressFill').style.width = progress + '%';
}

function highlightOperation(index) {
    document.querySelectorAll('.operation').forEach(op => {
        op.classList.remove('active');
    });
    
    const current = document.getElementById(`op-${index}`);
    if (current) {
        current.classList.add('active');
        current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function playAnimation() {
    if (isPlaying) return;
    isPlaying = true;
    
    document.getElementById('playBtn').disabled = true;
    document.getElementById('pauseBtn').disabled = false;
    
    animationInterval = setInterval(() => {
        if (currentIndex >= operations.length) {
            pauseAnimation();
            return;
        }
        
        highlightOperation(currentIndex);
        updateProgress();
        currentIndex++;
    }, 1500);
}

function pauseAnimation() {
    isPlaying = false;
    clearInterval(animationInterval);
    
    document.getElementById('playBtn').disabled = false;
    document.getElementById('pauseBtn').disabled = true;
}

function resetAnimation() {
    pauseAnimation();
    currentIndex = 0;
    updateProgress();
    document.querySelectorAll('.operation').forEach(op => {
        op.classList.remove('active');
    });
}

function exportReport() {
    window.print();
}

renderOperations();

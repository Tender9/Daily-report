const { spawn, execSync } = require('child_process');
const path = require('path');

const isWin = process.platform === 'win32';
const rootDir = __dirname;
const backendDir = path.join(rootDir, 'backend');
const frontendDir = path.join(rootDir, 'frontend');

console.log('🚀 [1/2] 正在启动后端服务 (FastAPI / Port 2001)...');
const backendProc = spawn(isWin ? 'uv' : 'uv', ['run', 'uvicorn', 'app.main:app', '--reload', '--port', '2001'], {
  cwd: backendDir,
  shell: true,
  stdio: 'inherit'
});

console.log('🚀 [2/2] 正在启动前端服务 (Vue3 + Vite / Port 1001)...');
const frontendProc = spawn(isWin ? 'npm' : 'npm', ['run', 'dev'], {
  cwd: frontendDir,
  shell: true,
  stdio: 'inherit'
});

console.log('\n✅ 所有服务已并发启动！');
console.log('  - 前端地址: http://localhost:1001');
console.log('  - 后端 API: http://localhost:2001\n');
console.log('按 Ctrl+C 可一键停止所有服务...\n');

function cleanExit() {
  console.log('\n🛑 正在停止所有服务...');
  [backendProc, frontendProc].forEach(proc => {
    if (proc && proc.pid) {
      if (isWin) {
        try {
          execSync(`taskkill /F /T /PID ${proc.pid}`, { stdio: 'ignore' });
        } catch (e) {}
      } else {
        try {
          proc.kill('SIGTERM');
        } catch (e) {}
      }
    }
  });
  console.log('👋 所有服务已全部停止！');
  process.exit(0);
}

process.on('SIGINT', cleanExit);
process.on('SIGTERM', cleanExit);

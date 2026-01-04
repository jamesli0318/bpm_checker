本地測試

  # 直接用瀏覽器開啟
  open index.html

  # 或用 HTTP server
  python3 -m http.server 8080
  # 然後開啟 http://localhost:8080/index.html

  免費部署選項

  GitHub Pages (最簡單)

  git init
  git add index.html
  git commit -m "180 BPM Detector"
  git branch -M main
  git remote add origin https://github.com/你的帳號/180bpm.git
  git push -u origin main
  # 然後到 GitHub repo Settings > Pages > 選擇 main branch

  Vercel

  npm i -g vercel
  vercel

  Netlify

  直接把 index.html 拖放到 https://app.netlify.com/drop

  ---
  這個版本：
  - 單一 HTML 檔案，無需後端
  - 使用 Web Audio API 擷取麥克風
  - 用 JavaScript 即時偵測 BPM
  - 可部署到任何靜態網站託管服務
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
export default defineConfig({
  plugins:[react(),VitePWA({registerType:'autoUpdate',includeAssets:['favicon.svg'],manifest:{name:'TeslaDrive',short_name:'TeslaDrive',description:'Dashboard Tesla personale',theme_color:'#111111',background_color:'#ffffff',display:'standalone',start_url:'/',icons:[{src:'/icon-192.png',sizes:'192x192',type:'image/png'},{src:'/icon-512.png',sizes:'512x512',type:'image/png'}]},workbox:{globPatterns:['**/*.{js,css,html,png,svg,ico}']}})]
})

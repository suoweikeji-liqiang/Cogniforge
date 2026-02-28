import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { Capacitor } from '@capacitor/core'
import { StatusBar, Style } from '@capacitor/status-bar'
import { Keyboard } from '@capacitor/keyboard'
import App from '@/App.vue'
import router from '@/router'
import i18n from '@/i18n'
import '@/assets/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

if (Capacitor.isNativePlatform()) {
  StatusBar.setStyle({ style: Style.Dark }).catch(() => {})
  StatusBar.setBackgroundColor({ color: '#0f0f23' }).catch(() => {})
  Keyboard.setAccessoryBarVisible({ isVisible: true }).catch(() => {})
}

app.mount('#app')

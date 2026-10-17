import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElLoading } from 'element-plus'

import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/es/components/loading/style/css'
import './style.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(ElLoading)
app.use(createPinia())
app.use(router)
app.mount('#app')

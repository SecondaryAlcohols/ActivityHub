<template>
  <div class="not-found">
    <div class="code">404</div>
    <h1>页面不存在</h1>
    <p class="muted">你访问的地址可能已被移除，或者从未存在。</p>
    <el-button type="primary" @click="$router.replace('/activities')">
      返回活动管理
    </el-button>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 12px;
  text-align: center;
}

.code {
  font-size: 72px;
  font-weight: 700;
  line-height: 1;
  color: #d6dcf5;
  letter-spacing: -2px;
}

h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}

p {
  margin: 0 0 16px;
  font-size: 14px;
}
</style>

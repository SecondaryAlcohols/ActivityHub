<template>
  <div class="page not-found">
    <div class="code">404</div>
    <h1>页面不存在</h1>
    <p class="muted">你访问的地址可能已被移除，或者从未存在。</p>
    <router-link to="/" class="primary-btn home-btn">返回活动广场</router-link>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 55vh;
  text-align: center;
}

.code {
  color: #d4daf2;
  font-size: 64px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -2px;
}

h1 {
  margin: 10px 0 6px;
  font-size: 20px;
  font-weight: 650;
}

p {
  margin: 0 0 20px;
  font-size: 13px;
}

.home-btn {
  width: 180px;
}
</style>

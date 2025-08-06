// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: "/",
  plugins: [react()],
  preview: {
    port: 8080,
    strictPort: true,
  },
  // server: {
  //   host: '0.0.0.0', // Allow access from outside container
  //   port: 5173,      // Internal container port
  //   proxy: {
  //     '/register': {
  //       target: 'http://user_service:5001',
  //       changeOrigin: true,
  //       secure: false,
  //     },
  //     '/login': {
  //       target: 'http://user_service:5001',
  //       changeOrigin: true,
  //       secure: false,
  //     },
  //     '/products': {
  //       target: 'http://product_service:5002',
  //       changeOrigin: true,
  //       secure: false,
  //     },
  //   },
  // },
});

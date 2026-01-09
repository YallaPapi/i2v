import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/contexts/AuthContext'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { VideoGeneration } from '@/pages/VideoGeneration'
import { ImageGeneration } from '@/pages/ImageGeneration'
import { Jobs } from '@/pages/Jobs'
import { Playground } from '@/pages/Playground'
import { Login } from '@/pages/Login'
import { Signup } from '@/pages/Signup'
import { Templates } from '@/pages/Templates'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 5, // 5 seconds
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Auth routes - no layout */}
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />

            {/* App routes - with layout */}
            <Route
              path="*"
              element={
                <Layout>
                  <Routes>
                    <Route path="/" element={<Playground />} />
                    <Route path="/playground" element={<Playground />} />
                    <Route path="/dashboard" element={<Dashboard />} />
                    <Route path="/video" element={<VideoGeneration />} />
                    <Route path="/image" element={<ImageGeneration />} />
                    <Route path="/jobs" element={<Jobs />} />
                    <Route path="/templates" element={<Templates />} />
                  </Routes>
                </Layout>
              }
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App

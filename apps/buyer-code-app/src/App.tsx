import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Search from './pages/Search'
import Cart from './pages/Cart'
import Rfq from './pages/Rfq'
import Orders from './pages/Orders'
import Insights from './pages/Insights'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/home" replace />} />
        <Route path="home" element={<Home />} />
        <Route path="search" element={<Search />} />
        <Route path="cart" element={<Cart />} />
        <Route path="rfq/new" element={<Rfq />} />
        <Route path="orders" element={<Orders />} />
        <Route path="insights" element={<Insights />} />
      </Route>
    </Routes>
  )
}

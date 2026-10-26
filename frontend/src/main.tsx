import { createRoot } from 'react-dom/client';
import { Dashboard, Overlay } from './ui';
import './style.css';

createRoot(document.getElementById('root')!).render(
  window.location.pathname === '/overlay' ? <Overlay /> : <Dashboard />,
);

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ReactNode, useState } from 'react';
import styles from './layout.module.css';

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [isCollapsed, setIsCollapsed] = useState(false);
  
  const navItems = [
    { 
      href: '/', 
      label: 'Portfolio', 
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M3 3v18h18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="m19 9-5 5-4-4-3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
    { 
      href: '/agents', 
      label: 'AI Hedge Fund', 
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
          <path d="M12 1v6m0 6v6" stroke="currentColor" strokeWidth="2"/>
          <path d="m21 12-6 0m-6 0-6 0" stroke="currentColor" strokeWidth="2"/>
        </svg>
      )
    },
    { 
      href: '/nrt', 
      label: 'NRT Strategy', 
      icon: (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )
    },
  ];

  return (
    <div className={styles.dashboardLayout}>
      <nav className={`${styles.navigation} ${isCollapsed ? styles.collapsed : ''}`}>
        <div className={styles.navHeader}>
          <div className={styles.navBrand}>
            <div className={styles.logo}>
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="url(#gradient)"/>
                <path d="M16 8l8 8-8 8-8-8z" fill="white"/>
                <defs>
                  <linearGradient id="gradient" x1="0" y1="0" x2="32" y2="32">
                    <stop stopColor="#6366f1"/>
                    <stop offset="1" stopColor="#8b5cf6"/>
                  </linearGradient>
                </defs>
              </svg>
            </div>
            {!isCollapsed && (
              <div className={styles.brandInfo}>
                <span className={styles.brandText}>Hedge AI</span>
                <span className={styles.brandSub}>Pro Trading</span>
              </div>
            )}
          </div>
          
          <button 
            className={styles.collapseBtn}
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="m15 18-6-6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
        
        <div className={styles.navItems}>
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`${styles.navItem} ${pathname === item.href ? styles.active : ''}`}
            >
              <span className={styles.navIcon}>{item.icon}</span>
              {!isCollapsed && <span className={styles.navLabel}>{item.label}</span>}
            </Link>
          ))}
        </div>
        
        <div className={styles.navFooter}>
          <div className={styles.marketStatus}>
            <div className={styles.statusRow}>
              <span className={styles.statusDot}></span>
              {!isCollapsed && <span className={styles.statusText}>Market Open</span>}
            </div>
            {!isCollapsed && (
              <div className={styles.statusDetails}>
                <div>S&P 500: +0.85%</div>
                <div>Last update: 2s ago</div>
              </div>
            )}
          </div>
        </div>
      </nav>
      
      <main className={styles.mainContent}>
        <div className={styles.contentWrapper}>
          {children}
        </div>
      </main>
    </div>
  );
}
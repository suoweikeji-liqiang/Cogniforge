# UI Contract - Cogniforge

## Button System

### Base Button (.btn)
- **Font size**: 0.95rem
- **Padding**: 0.75rem 1.5rem
- **Border radius**: 6px
- **Cursor**: pointer
- **Transition**: all 0.2s

### Disabled State
- **Opacity**: 0.5
- **Cursor**: not-allowed
- **No hover effects**: Disabled buttons must not respond to hover

### Primary Button (.btn-primary)
- **Background**: var(--primary) #4ade80
- **Text color**: var(--bg-dark) #0f0f23
- **Hover**: Background changes to var(--primary-dark) #22c55e
- **Hover disabled**: No hover effect when disabled

### Secondary Button (.btn-secondary)
- **Background**: var(--bg-card) #1a1a2e
- **Text color**: var(--text) #e5e5e5
- **Border**: 1px solid var(--border) #2a2a4e
- **Hover**: Border color changes to var(--primary)
- **Hover disabled**: No hover effect when disabled

## Accessibility Requirements
- All buttons must have visible focus states
- Disabled buttons must have cursor: not-allowed
- Button text must have sufficient contrast ratio (4.5:1 minimum)

## Critical Paths
- Dashboard navigation
- Problem creation/submission
- Model card operations
- Review generation

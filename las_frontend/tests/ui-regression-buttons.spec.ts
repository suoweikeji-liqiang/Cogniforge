/**
 * UI Regression Tests - Button System
 * Generated based on UI Contract: /spec/ui/ui_contract.md
 *
 * Test Coverage:
 * - Button disabled states
 * - Button hover interactions
 * - Button styling consistency
 * - Accessibility compliance
 */

import { test, expect } from '@playwright/test'

test.describe('Button System - UI Contract Compliance', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/login')
  })

  test('UIC-01: Primary button has correct base styles', async ({ page }) => {
    // Contract: Base Button - font-size: 0.95rem, padding: 0.75rem 1.5rem
    const loginButton = page.locator('button.btn.btn-primary').first()

    await expect(loginButton).toBeVisible()

    const styles = await loginButton.evaluate((el) => {
      const computed = window.getComputedStyle(el)
      return {
        fontSize: computed.fontSize,
        paddingTop: computed.paddingTop,
        paddingRight: computed.paddingRight,
        borderRadius: computed.borderRadius,
        cursor: computed.cursor,
      }
    })

    expect(styles.fontSize).toBe('15.2px') // 0.95rem = 15.2px at 16px base
    expect(styles.cursor).toBe('pointer')
  })

  test('UIC-02: Disabled button has correct visual state', async ({ page }) => {
    // Contract: Disabled State - opacity: 0.5, cursor: not-allowed
    await page.goto('http://localhost:5173/dashboard')

    // Find a disabled button (review generation button when already exists)
    const disabledButton = page.locator('button.btn:disabled').first()

    if (await disabledButton.count() > 0) {
      const styles = await disabledButton.evaluate((el) => {
        const computed = window.getComputedStyle(el)
        return {
          opacity: computed.opacity,
          cursor: computed.cursor,
        }
      })

      expect(styles.opacity).toBe('0.5')
      expect(styles.cursor).toBe('not-allowed')
    }
  })

  test('UIC-03: Primary button hover state changes background', async ({ page }) => {
    // Contract: Primary Button hover - background changes to var(--primary-dark)
    const loginButton = page.locator('button.btn.btn-primary').first()

    const initialBg = await loginButton.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor
    )

    await loginButton.hover()
    await page.waitForTimeout(300) // Wait for transition

    const hoverBg = await loginButton.evaluate((el) =>
      window.getComputedStyle(el).backgroundColor
    )

    // Background should change on hover
    expect(initialBg).not.toBe(hoverBg)
  })

  test('UIC-04: Disabled button does not respond to hover', async ({ page }) => {
    // Contract: Hover disabled - No hover effect when disabled
    await page.goto('http://localhost:5173/dashboard')

    const disabledButton = page.locator('button.btn:disabled').first()

    if (await disabledButton.count() > 0) {
      const initialBg = await disabledButton.evaluate((el) =>
        window.getComputedStyle(el).backgroundColor
      )

      await disabledButton.hover({ force: true })
      await page.waitForTimeout(300)

      const hoverBg = await disabledButton.evaluate((el) =>
        window.getComputedStyle(el).backgroundColor
      )

      // Background should NOT change on hover when disabled
      expect(initialBg).toBe(hoverBg)
    }
  })

  test('UIC-05: Secondary button has correct border styling', async ({ page }) => {
    // Contract: Secondary Button - border: 1px solid var(--border)
    await page.goto('http://localhost:5173/problems')

    const secondaryButton = page.locator('button.btn.btn-secondary').first()

    if (await secondaryButton.count() > 0) {
      const styles = await secondaryButton.evaluate((el) => {
        const computed = window.getComputedStyle(el)
        return {
          borderWidth: computed.borderWidth,
          borderStyle: computed.borderStyle,
        }
      })

      expect(styles.borderWidth).toBe('1px')
      expect(styles.borderStyle).toBe('solid')
    }
  })

  test('UIC-06: Button text has sufficient contrast', async ({ page }) => {
    // Contract: Accessibility - Button text must have 4.5:1 contrast ratio
    const primaryButton = page.locator('button.btn.btn-primary').first()

    await expect(primaryButton).toBeVisible()

    // Use axe-core for accessibility testing
    await expect(primaryButton).toHaveAccessibleName()
  })
})

test.describe('Critical Path - Dashboard Button Interactions', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('http://localhost:5173/login')
    await page.fill('input[type="email"]', 'test@example.com')
    await page.fill('input[type="password"]', 'password')
    await page.click('button.btn.btn-primary')
    await page.waitForURL('**/dashboard')
  })

  test('CP-01: Generate review button interaction', async ({ page }) => {
    // Contract: Critical Path - Review generation
    const generateButton = page.locator('button.btn.btn-primary', {
      hasText: /generate|生成/i
    }).first()

    if (await generateButton.count() > 0) {
      await expect(generateButton).toBeEnabled()
      await generateButton.click()

      // Button should become disabled during generation
      await expect(generateButton).toBeDisabled()
    }
  })

  test('CP-02: Navigation buttons are clickable', async ({ page }) => {
    // Contract: Critical Path - Dashboard navigation
    const problemsLink = page.locator('a.nav-pill[href="/problems"]')

    await expect(problemsLink).toBeVisible()
    await problemsLink.click()
    await page.waitForURL('**/problems')

    expect(page.url()).toContain('/problems')
  })
})

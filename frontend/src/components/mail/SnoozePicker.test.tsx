import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { SnoozePicker } from './SnoozePicker.tsx'

describe('SnoozePicker (MAIL-28)', () => {
  it('offers the presets and returns an ISO time', () => {
    const onPick = vi.fn(); const onClose = vi.fn()
    render(<SnoozePicker count={1} onPick={onPick} onClose={onClose} />)
    expect(screen.getByRole('dialog', { name: 'Snooze until' })).toBeInTheDocument()
    fireEvent.click(screen.getByText('Tomorrow'))
    expect(onPick).toHaveBeenCalledTimes(1)
    const iso = onPick.mock.calls[0][0] as string
    expect(new Date(iso).getTime()).toBeGreaterThan(Date.now())
    expect(new Date(iso).getHours()).toBe(8)
  })

  it('rejects a custom time in the past and accepts one in the future', () => {
    const onPick = vi.fn()
    render(<SnoozePicker count={2} onPick={onPick} onClose={() => {}} />)
    expect(screen.getByText('Snooze 2 threads until')).toBeInTheDocument()
    const input = screen.getByLabelText('Pick a date and time')
    fireEvent.change(input, { target: { value: '2001-01-01T09:00' } })
    expect(screen.getByText('Choose a time in the future.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Snooze' })).toBeDisabled()
    fireEvent.change(input, { target: { value: '2099-01-01T09:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Snooze' }))
    expect(onPick).toHaveBeenCalledWith(new Date('2099-01-01T09:00').toISOString())
  })

  it('closes on Escape and on the backdrop', () => {
    const onClose = vi.fn()
    render(<SnoozePicker count={1} onPick={() => {}} onClose={onClose} />)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('presentation'))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})

-- Eartag pad tab: a clickable "Recap │ Pad" bar on top of the pad, and keys back to the recap.
-- Sourced with -S after the user's config. Leaving nvim hands the pane back to the panel.

local function back_to_recap()
  pcall(function() vim.cmd('silent! wall') end)
  vim.cmd('qall')
end
_G.EartagRecap = function() back_to_recap() end

vim.o.mouse = 'a'
vim.wo.winbar = '%#TabLine#%@v:lua.EartagRecap@  Recap  %X%#TabLineSel#  Pad  %#TabLineFill# %t'

-- \r and <Tab> (normal mode) go back to the recap.
vim.keymap.set('n', '<localleader>r', back_to_recap, { buffer = true, desc = 'Eartag: back to recap' })
vim.keymap.set('n', '<Tab>', back_to_recap, { buffer = true, desc = 'Eartag: back to recap' })

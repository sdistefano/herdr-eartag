-- Eartag's pad nvim in the Herdr app panel (sourced with -S by that nvim only; see
-- payload.app_nvim). The panel is narrow and shows one pad: no tab/buffer line, no line
-- numbers or sign column, and one buffer at a time. The person's nvim config is untouched
-- everywhere else.

-- The tab's scratch pane has the same pad open: no swap here, no W325 when opening another.
vim.opt.swapfile = false
vim.opt.shortmess:append("A")

-- Window-local look, applied again whenever a window shows a buffer: plugins (LazyVim's
-- statuscolumn, bufferline) set these on their own events.
local function bare()
  vim.o.showtabline = 0
  vim.wo.number = false
  vim.wo.relativenumber = false
  vim.wo.signcolumn = "no"
  vim.wo.foldcolumn = "0"
  vim.wo.statuscolumn = ""
end

local group = vim.api.nvim_create_augroup("EartagPadApp", { clear = true })
vim.api.nvim_create_autocmd({ "BufWinEnter", "WinEnter", "BufAdd", "VimEnter" }, {
  group = group,
  callback = function()
    vim.schedule(bare) -- after the plugins' own handlers for the same event
  end,
})
bare()

-- Open another agent's pad (the panel sends this through --remote-send): save the one
-- shown, open the new one, and wipe the others so buffers never pile up.
function EartagOpen(path)
  pcall(vim.cmd, "silent! update")
  vim.cmd("edit " .. vim.fn.fnameescape(path))
  local keep = vim.api.nvim_get_current_buf()
  for _, buf in ipairs(vim.api.nvim_list_bufs()) do
    if buf ~= keep and vim.bo[buf].buflisted and not vim.bo[buf].modified then
      pcall(vim.api.nvim_buf_delete, buf, {})
    end
  end
  bare()
end

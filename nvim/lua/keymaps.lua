-- jump to end/beginning of line
vim.keymap.set('i', '<C-e>', '<C-o>$')
vim.keymap.set('i', '<C-a>', '<C-o>0')

-- exit from terminal
vim.keymap.set('t', '<C-x>', '<C-\\><C-n>')

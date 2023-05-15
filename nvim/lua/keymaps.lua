-- jump to end/beginning of line
vim.keymap.set('i', '<C-e>', '<C-o>$')
vim.keymap.set('i', '<C-a>', '<C-o>0')

-- exit from terminal
vim.keymap.set('t', '<C-x>', '<C-\\><C-n>')

-- tab navigation & creation
vim.keymap.set('n', '<TAB>',   ':tabnext<CR>')
vim.keymap.set('n', '<S-TAB>', ':tabNext<CR>')
vim.keymap.set('n', '<C-t>',   ':tabnew<CR>')

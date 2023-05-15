require('telescope').setup()

vim.keymap.set('n', '<leader>ff', ':Telescope find_files<CR>')
vim.keymap.set('n', '<leader>fg', ':Telescope live_grep<CR>')
vim.keymap.set('n', '<leader>fs', ':Telescope grep_string<CR>')
vim.keymap.set('n', '<leader>fc', ':Telescope command_history<CR>')

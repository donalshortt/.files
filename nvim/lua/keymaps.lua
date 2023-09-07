local keymap = vim.keymap.set


-- BASIC

-- jump to end/beginning of line
keymap('i', '<C-e>', '<C-o>$')
keymap('i', '<C-a>', '<C-o>0')

keymap('n', '<C-Down>','<C-e>')
keymap('n', '<C-Up>', '<C-y>')
keymap('i', '<C-Down>','<C-e>')
keymap('i', '<C-Up>', '<C-y>')

-- LSP SAGA

-- rename all occurrences of the hovered word for the entire file
keymap("n", "gr", "<cmd>Lspsaga rename<CR>")

-- shows references, implementation & definition
keymap("n", "gf", "<cmd>Lspsaga lsp_finder<CR>")

-- go to definition
keymap("n", "gd", "<cmd>Lspsaga goto_definition<CR>")
-- peek definition
keymap("n", "gp", "<cmd>Lspsaga peek_definition<CR>")

-- show line diagnostics
keymap("n", "<leader>sl", "<cmd>Lspsaga show_line_diagnostics<CR>")
-- show cursor diagnostics
keymap("n", "<leader>sc", "<cmd>Lspsaga show_cursor_diagnostics<CR>")
-- show buffer diagnostics
keymap("n", "<leader>sb", "<cmd>Lspsaga show_buf_diagnostics<CR>")

-- diagnostic jump
keymap("n", "s[", "<cmd>Lspsaga diagnostic_jump_prev<CR>")
keymap("n", "s]", "<cmd>Lspsaga diagnostic_jump_next<CR>")

-- toggle outline
keymap("n","<leader>o", "<cmd>Lspsaga outline<CR>")

-- toggle hover doc
keymap("n", "<leader>d", "<cmd>Lspsaga hover_doc<CR>")

-- toggle terminal
keymap({"n", "t"}, "<leader>;", "<cmd>Lspsaga term_toggle<CR>")

-- exit from terminal
keymap('t', '<C-x>', '<C-\\><C-n>')

-- code actions
keymap('n', '<leader>a', '<cmd>Lspsaga code_action<CR>')

-- TELESCOPE
keymap('n', '<leader>ff', ':Telescope find_files<CR>')
keymap('n', '<leader>fg', ':Telescope live_grep<CR>')
keymap('n', '<leader>fs', ':Telescope grep_string<CR>')
keymap('n', '<leader>fc', ':Telescope command_history<CR>')


-- BARBAR
keymap('n', '<TAB>',   ':BufferNext<CR>')
keymap('n', '<S-TAB>', ':BufferPrevious<CR>')
keymap('n', '<C-t>',   ':tabnew<CR>')


-- NVIM TREE
keymap('n', '<leader>v', ':NvimTreeToggle<CR>')


-- LAZYGIT 
keymap('n', '<leader>ll', ':LazyGit<CR>')

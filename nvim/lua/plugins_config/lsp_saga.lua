require("lspsaga").setup({})

local keymap = vim.keymap.set

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

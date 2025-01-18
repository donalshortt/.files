local Hydra = require("hydra")

Hydra.setup({})


Hydra({
    -- string? only used in auto-generated hint
    name = "Test",

    -- string | string[] modes where the hydra exists, same as `vim.keymap.set()` accepts
    mode = "n",

    -- string? key required to activate the hydra, when excluded, you can use
    -- Hydra:activate()
    body = "<leader>w",

    -- these are explained below
    hint = [[ look at this nice hint ]],
	config = {
		hint = {
			position = "top",
			offset = 4
	}
	},
    heads = {
		{"d", ":echo 'hellooooijoijio'", {desc = "yeeeats"}},
		{"f", ":echo 'hellooooijoijio'",{desc = "wow"}},
		{"a", ":echo 'hellooooijoijio'",{desc = "yeee"}},
		{"h", ":echo 'hellooooijoijio'", {desc = "test"}},
	},
})

-- Hydra({
--     -- string? only used in auto-generated hint
--     name = "Debug",

--     -- string | string[] modes where the hydra exists, same as `vim.keymap.set()` accepts
--     mode = "n",

--     -- string? key required to activate the hydra, when excluded, you can use
--     -- Hydra:activate()
--     body = "<leader>x",

--     -- these are explained below
--     hint = [[ "wawaweewoo" ]],
--     heads = {
-- 		{"d", ":DapContinue"},
-- 		{"s", ":DapStepInto"},
-- 		{"a", ":DapStepOver"},
-- 		{"r", ":DapToggleRepl"},
-- 		{"w", ":DapTerminate"}
-- 	},
-- })

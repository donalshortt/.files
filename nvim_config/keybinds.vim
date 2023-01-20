" jump to beginning/end of line
inoremap <C-e> <C-o>$
inoremap <C-a> <C-o>0

" toggle chadtree
noremap <leader>v <cmd>CHADopen<cr>

" toggle lazygit
nnoremap <silent> <leader>ll :LazyGit<CR>

" exit from terminal
tnoremap <C-x> <C-\><C-n>

" tab navigation 
nnoremap <tab>     	:tabnext<CR>
nnoremap <S-tab> 	:tabNext<CR>
nnoremap <C-t>     	:tabnew<CR>

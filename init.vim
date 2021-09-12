call plug#begin(stdpath('data') . '/plugged')

    Plug 'preservim/nerdtree'
    Plug 'dstein64/nvim-scrollview', { 'branch': 'main' }
    Plug 'bfrg/vim-cpp-modern'
    "Plug 'ycm-core/YouCompleteMe'
    Plug 'Xuyuanp/nerdtree-git-plugin'
    Plug 'ryanoasis/vim-devicons'

call plug#end()

"nnoremap <C-b>  :YcmCompleter GoToDefinitionElseDeclaration<CR>
"nnoremap <C-r>  :YcmCompleter GoToReferences<CR>
" Apply YCM FixIt
"map <F9> :YcmCompleter FixIt<CR>

" jump to beginning/end of line while in insert
inoremap <C-e> <C-o>$
inoremap <C-a> <C-o>0

set tabstop=4
set shiftwidth=4
set expandtab
set number
set relativenumber
set autoread
set hlsearch

syntax on
"filetype plugin indent on

" Enable highlighting of C++11 attributes
let g:cpp_attributes_highlight = 1

" Highlight struct/class member variables (affects both C and C++ files)
let g:cpp_member_highlight = 1

" clang autocomplete stuff
let g:clang_library_path = '/usr/lib/x86_64-linux-gnu/'
let g:clang_c_options = '-std=gnu11'
let g:clang_cpp_options = '-std=c++11 -stdlib=libc++'
let g:clang_complete = 1 "automatically selects the first entry in the popup menu
let g:clang_snippets = 1 "do some snippets magic on code placehorlders like funcion argument, template parameters, etc.
let g:clang_close_preview = 1

" open auto, start cursor in file, close if last window open
au VimEnter NERD_tree_1 enew | execute 'NERDTree '.argv()[0] 
" autocmd VimEnter * wincmd p
autocmd bufenter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif

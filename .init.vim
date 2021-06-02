set number
set relativenumber
set tabstop=4
set shiftwidth=4
set autoread
set nocompatible              " be iMproved, required
set hlsearch

syntax on

filetype off                  " required

autocmd VimEnter * NERDTree | wincmd p
autocmd BufEnter * if tabpagenr('$') == 1 && winnr('$') == 1 && exists('b:NERDTree') && b:NERDTree.isTabTree() |
    \ quit | endif

nnoremap <C-b>  :YcmCompleter GoToDefinitionElseDeclaration<CR>
nnoremap <C-r>  :YcmCompleter GoToReferences<CR>
" Apply YCM FixIt
map <F9> :YcmCompleter FixIt<CR>

" jump to beginning/end of line while in insert
inoremap <C-e> <C-o>$
inoremap <C-a> <C-o>0

" remap undo
nnoremap z :u<CR>

" set the runtime path to include Vundle and initialize
set rtp+=~/.vim/bundle/Vundle.vim
call vundle#begin()
" alternatively, pass a path where Vundle should install plugins
"call vundle#begin('~/some/path/here')

" let Vundle manage Vundle, required
Plugin 'VundleVim/Vundle.vim'

" The following are examples of different formats supported.
" Keep Plugin commands between vundle#begin/end.
" plugin on GitHub repo
Plugin 'tpope/vim-fugitive'
" plugin from http://vim-scripts.org/vim/scripts.html
" Plugin 'L9'
" Git plugin not hosted on GitHub
Plugin 'git://git.wincent.com/command-t.git'
" git repos on your local machine (i.e. when working on your own plugin)
" Plugin 'file:///home/gmarik/path/to/plugin'
" The sparkup vim script is in a subdirectory of this repo called vim.
" Pass the path to set the runtimepath properly.
Plugin 'rstacruz/sparkup', {'rtp': 'vim/'}
" Install L9 and avoid a Naming conflict if you've already installed a
" different version somewhere else.
" Plugin 'ascenator/L9', {'name': 'newL9'}

Plugin 'ycm-core/YouCompleteMe'
Plugin 'ghifarit53/tokyonight-vim'
Plugin 'preservim/nerdtree'
Plugin 'ryanoasis/vim-devicons'
Plugin 'arcticicestudio/nord-vim'
Plugin 'Xuyuanp/nerdtree-git-plugin'

" All of your Plugins must be added before the following line
call vundle#end()            " required
filetype plugin indent on    " required
" To ignore plugin indent changes, instead use:
"filetype plugin on
"
" Brief help
" :PluginList       - lists configured plugins
" :PluginInstall    - installs plugins; append `!` to update or just :PluginUpdate
" :PluginSearch foo - searches for foo; append `!` to refresh local cache
" :PluginClean      - confirms removal of unused plugins; append `!` to auto-approve removal


let g:tokyonight_style = 'storm' " available: night, storm
let g:tokyonight_enable_italic = 1

" see :h vundle for more details or wiki for FAQ
" Put your non-Plugin stuff after this line
colorscheme nord

" clang autocomplete stuff
let g:clang_library_path = '/usr/lib/x86_64-linux-gnu/'
let g:clang_c_options = '-std=gnu11'
let g:clang_cpp_options = '-std=c++11 -stdlib=libc++'
let g:clang_complete = 1 "automatically selects the first entry in the popup menu
let g:clang_snippets = 1 "do some snippets magic on code placehorlders like funcion argument, template parameters, etc.
let g:clang_close_preview = 1

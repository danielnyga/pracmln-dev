# 
#
# (C) 2011-2015 by Daniel Nyga (nyga@cs.uni-bremen.de)
# 
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

from Tkinter import Tk, Frame, Label, Button, StringVar
from Tkconstants import BOTH, END, INSERT
from pracmln.utils.widgets import SyntaxHighlightingText, ScrolledText2
from pracmln.logic.fol import FirstOrderLogic


class FormulaEditor(object):
    
    def __init__(self):
        root = Tk()
        self.root = root
        self.initialized = False
        
        root.title("Logical Formula Editor for LaTeX")
        
        self.frame = Frame(root)
        self.frame.pack(fill=BOTH, expand=0)
        self.frame.columnconfigure(0, weight=1)
        
        row = 0
        Label(self.frame, text='Type in the logical formula to convert to LaTeX code:').grid(row=row, column=0, sticky='WE')
        
        row += 1
        self.editor = SyntaxHighlightingText(self.frame)
        self.editor.grid(row=row, column=0, sticky='WE')
        self.frame.rowconfigure(row, weight=1)
        self.editor.config(height=10)
        self.editor.insert(END, '(a(x) ^ b(u) v !(c(h) v (r =/= k) ^ !(d(i) ^ !e(x) ^ g(x)))) => EXIST ?a,?b (f(x) ^ b(c))')        
        
        row += 1
        panel = Frame(self.frame)
        panel.grid(row=row, column=0, sticky='W')
        btn_convert = Button(panel, text='Convert to LaTeX', command=self.convert)
        btn_convert.grid(row=0)
        
        row += 1
        self.txt_converted = ScrolledText2(self.frame)
        self.txt_converted.config(height=20)
        self.txt_converted.grid(row=row, sticky='NEWS', column=0)
        self.frame.rowconfigure(row, weight=1)


    def run(self):
        self.root.mainloop()

    
    def convert(self):
        logic = FirstOrderLogic('PRACGrammar', None)
        formula = self.editor.get("1.0", END)
        formula = logic.parse_formula(formula)
        formula.print_structure()
        print formula.cstr(True)
        print formula
        self.txt_converted.delete('1.0', END)
        self.txt_converted.insert(INSERT, formula.latex())
        
        

if __name__ == '__main__':
    FormulaEditor().run()
    
import tkinter as tk
import sys, os, glob, re, psutil
import threading
import numpy as np
from tkinter import filedialog, Entry, simpledialog
import tkinter.messagebox
import customtkinter as ctk
import webbrowser
import traceback
from tkinter import messagebox
from tkinter import StringVar
from datetime import datetime
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import logging
import time
import gc
from PIL import Image, ImageTk
import multiprocessing
from functools import partial


ctk.set_appearance_mode("Light")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class PlaceholderEntry(ctk.CTkEntry):
    def __init__(self, master=None, placeholder_text="", callback=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        temp_entry = ctk.CTkEntry(self)
        self.default_fg_color = temp_entry.cget("fg_color") # get default fg color of widgets
        temp_entry.destroy()

        self.placeholder_text = placeholder_text
        self.callback = callback  # Store the callback function
        self.is_placeholder = True  # Initially, the placeholder is shown
        
        # Set up a StringVar for the textvariable if not already set
        self.entry_var = self.cget("textvariable")
        if not self.entry_var:
            self.entry_var = ctk.StringVar()
            self.configure(textvariable=self.entry_var)
        
        self.programmatic_update = False  # Flag to track programmatic updates
        
        # Bind focus events
        self.bind("<FocusIn>", self.on_focus_in)
        self.bind("<FocusOut>", self.on_focus_out)
        self.bind("<Escape>", self.on_escape)  # Bind the Escape key to focus out

        # Attach trace for value changes
        self.entry_var.trace_add("write", self.on_var_change_with_callback if self.callback else self.on_var_change)

        self.show_placeholder()


    def on_escape(self, event):
        """Handle the Escape key event to focus out."""
        self.master.focus()  # Focus out to the parent widget


    def show_placeholder(self):
        if not self.entry_var.get():
            self.entry_var.set(self.placeholder_text)
            self.update_font_color(placeholder=True)

    def on_focus_in(self, event):
        if self.entry_var.get() == self.placeholder_text:
            self.delete(0, "end")
            self.update_font_color(placeholder=False)
            self.is_placeholder = False

    def on_focus_out(self, event):
        if not self.entry_var.get():
            self.show_placeholder()
            self.is_placeholder = True

    def on_var_change(self, *args):
        # Update font color based on the current text
        mode = ctk.get_appearance_mode()
        textcolor = "white" if mode == "Light" else "black"
        if self.entry_var.get() != self.placeholder_text:
            self.configure(text_color=textcolor)
            self.update_font_color(placeholder=False)

    def on_var_change_with_callback(self, *args):
        # Call the default handler
        self.on_var_change(*args)
        # Call the provided callback function only if the value actually changes
        if self.callback and self.entry_var.get() != "" and self.entry_var.get() != self.placeholder_text:
            self.callback(self.entry_var.get())

    def update_font_color(self, placeholder):
        # Update the font color based on placeholder status
        mode = ctk.get_appearance_mode()
        color = self.default_fg_color if placeholder else ("white" if mode == "Light" else "gray17")
        textcolor = "grey" if placeholder else ("black" if mode == "Light" else "white")
        if self.cget("state") == "normal":
            self.configure(fg_color=color, text_color=textcolor)
        elif self.cget("state") == "disabled":
            self.configure(text_color="grey40")
        
    def set_value(self, value):
        """Programmatically set the entry value and mark it as such."""
        self.programmatic_update = True  # Set the flag before updating
        self.entry_var.set(value)
        self.programmatic_update = False  # Reset the flag after updating
        self.is_placeholder = False

    def get_value(self):
        """Returns the actual value of the entry, not the placeholder text."""
        return self.entry_var.get() if not self.is_placeholder else None


class NamedScrollbars:
    def __init__(self, name, hbar, vbar):
        self.name = name
        self.hbar_widget = hbar
        self.vbar_widget = vbar

    def __repr__(self):
        return f"{self.name}: Horizontal Scrollbar: {self.hbar_widget}, Vertical Scrollbar: {self.vbar_widget}"


class NamedWidget:
    def __init__(self, name, widget):
        self.name = name
        self.widget = widget

    def __repr__(self):
        return f"{self.name}: {self.widget}"


class ScrollbarsStatus:
    def __init__(self, frames_list, canvases_list):
        # Initialize size attributes
        self.frames = frames_list
        self.canvases = canvases_list
        self.content_width = 0
        self.content_height = 0
        self.canvas_width = 0
        self.canvas_height = 0

    def update_sizes(self, frame, canvas):
        # Update the current size of the content frame and the canvas viewport
        frame_widget = self.get_widget_by_name(frame, self.frames)
        canvas_widget = self.get_widget_by_name(canvas, self.canvases)
        # print("frame is: ", frame)
        # print("canvas is: ", canvas)
        try:
            self.content_width = frame_widget.winfo_reqwidth()
            self.content_height = frame_widget.winfo_reqheight()
            self.canvas_width = canvas_widget.winfo_width()
            self.canvas_height = canvas_widget.winfo_height()
        except tk.TclError as e:
            # print(f"An error occurred: {e}")
            pass

    def horizontally(self, frame, canvas):
        self.update_sizes(frame=frame, canvas=canvas)
        # print("canvas height: ", self.canvas_height)
        # print("content height: ", self.content_height)
        return "ON" if self.content_width > self.canvas_width else "OFF"

    def vertically(self, frame, canvas):
        self.update_sizes(frame=frame, canvas=canvas)
        # print("canvas width: ", self.canvas_width)
        # print("content width: ", self.content_width)
        return "ON" if self.content_height > self.canvas_height else "OFF"

    def get_widget_by_name(self, name, mylist):
        # print("name is : ",name)
        for named_widget in mylist:
            # print("named_widget is : ",named_widget.name)
            if named_widget.name == name:
                return named_widget.widget


class ManagedCTkScrollbar(ctk.CTkScrollbar):
    def __init__(self, parent, orientation, command, frames_list, canvases_list, frames_names, canvas_name, **kwargs):
        super().__init__(parent, orientation=orientation, command=command, **kwargs)
        self.orientation = orientation
        self.frames = {frame['name']: frame['widget'] for frame in frames_list}
        self.canvases = {canvas['name']: canvas['widget'] for canvas in canvases_list}
        self.frames_names = frames_names
        self.canvas_name = canvas_name

        self.canvas_widget = self.get_widget_by_name(canvas_name, self.canvases)
        if not hasattr(self.canvas_widget, '_scrollbars'):
            self.canvas_widget._scrollbars = []
        self.canvas_widget._scrollbars.append(self)

        # Debounce variables
        self.last_resize_time = 0
        self.debounce_delay = 50  # milliseconds

        # Bind the canvas configure event with debounce
        self.canvas_widget.bind("<Configure>", self.debounced_update)

        # Bind mouse wheel events
        self.canvas_widget.bind("<Enter>", self.bind_mouse_wheel)  # Bind mouse events when the mouse enters the widget
        self.canvas_widget.bind("<Leave>", self.unbind_mouse_wheel)  # Unbind mouse events when the mouse leaves the widget

        # self.after(100, self.update_scrollbar_visibility)  # Run the checkup 100ms after startup
        # self.after(100,self.on_mouse_wheel)

    def get_widget_by_name(self, name, widgets_dict):
        return widgets_dict.get(name)

    def update_sizes(self):
        self.content_width = 0
        self.content_height = 0


        canvas_widget = self.get_widget_by_name(self.canvas_name, self.canvases)

        if not canvas_widget:
            print("Invalid canvas name provided.")
            return
        try:
            self.canvas_width = canvas_widget.winfo_width()
            self.canvas_height = canvas_widget.winfo_height()
        except tk.TclError as e:
            print(f"An error occurred: {e}")
            return
        
        # if not frame_widget:
        #     print("Invalid frame or canvas name provided.")
        #     return

        for frame_name in self.frames_names:
            frame_widget = self.get_widget_by_name(frame_name, self.frames)
            try: 
                if self.content_width < frame_widget.winfo_reqwidth():
                    self.content_width = frame_widget.winfo_reqwidth()
                if self.content_height == 0: 
                    self.content_height = frame_widget.winfo_reqheight() 
                else:
                    self.content_height += frame_widget.winfo_reqheight()
            except tk.TclError as e:
                print(f"An error occurred: {e}")
                return
        # print(f"Content width: {self.content_width}, Content height: {self.content_height}")
        # print(f"Canvas width: {self.canvas_width}, Canvas height: {self.canvas_height}")

        


    def update_scrollbar_visibility(self, event=None):
        try:
            self.update_sizes()

            for scrollbar in self.canvas_widget._scrollbars:
                orientation = scrollbar.cget("orientation")
                if orientation == "horizontal":
                    if self.content_width > self.canvas_width:
                        scrollbar.grid(row=1, column=0, sticky="ew")  # Enable horizontal scrollbar
                        self.canvases[self.canvas_name].configure(xscrollcommand=scrollbar.set)
                        
                        if event is not None:
                            try:    
                                if event.delta < 0:
                                    self.canvases[self.canvas_name].widget.yview_scroll(1, "units")
                            except Exception as e:
                                print(f"Error: {e} - problem with mouswheel on HOR.")

                    else:
                        scrollbar.grid_remove()  # Disable horizontal scrollbar
                        self.canvases[self.canvas_name].configure(xscrollcommand="")
                elif orientation == "vertical":
                    if self.content_height > self.canvas_height:
                        scrollbar.grid(row=0, column=1, sticky="ns")  # Enable vertical scrollbar
                        self.canvases[self.canvas_name].configure(yscrollcommand=scrollbar.set)

                        if event is not None:
                            try:    
                                if event.delta > 0:
                                    self.canvases[self.canvas_name].widget.yview_scroll(-1, "units")
                            except Exception as e:
                                print(f"Error: {e} - problem with mouswheel on VER.")

                    else:
                        scrollbar.grid_remove()  # Disable vertical scrollbar
                        self.canvases[self.canvas_name].configure(yscrollcommand="")

            # Update the scroll region
            # Assume frames_list is a list of the frame names/keys you want to include in the scrollregion.
            frame_bboxes = [self.frames[frame_name].bbox("all") for frame_name in self.frames_names]


            # for frame_name, bbox in zip(self.frames_names, frame_bboxes):
            #     print(f"{frame_name} bbox: {bbox}")



            # Initialize the combined bounding box with the first frame's bounding box
            x1, y1, x2, y2 = frame_bboxes[0]

            # Loop through the rest of the bounding boxes to find the overall bounding box
            for bbox in frame_bboxes[1:]:
                x1 = min(x1, bbox[0])
                x2 = max(x2, bbox[2])
                y1 += bbox[1]
                y2 += bbox[3]+20

            # Set the scrollregion to the combined bounding box
            self.canvases[self.canvas_name].configure(scrollregion=(x1, y1, x2, y2))

        except Exception as e:
            print(f"An error occurred in update_scrollbar_visibility: {e}")

    def debounced_update(self, event=None):
        current_time = int(time.time() * 1000)
        if current_time - self.last_resize_time > self.debounce_delay:
            self.update_sizes()
            self.update_scrollbar_visibility(event)
            self.last_resize_time = current_time
            
    def bind_mouse_wheel(self, event=None):
        """Binds the mouse wheel event when the mouse enters the widget."""
        self.canvas_widget.bind_all("<MouseWheel>", self.on_mouse_wheel)
        self.canvas_widget.bind_all("<Shift-MouseWheel>", self.on_shift_mouse_wheel)

    def unbind_mouse_wheel(self, event=None):
        """Unbinds the mouse wheel event when the mouse leaves the widget."""
        self.canvas_widget.unbind_all("<MouseWheel>")
        self.canvas_widget.unbind_all("<Shift-MouseWheel>")

    def on_mouse_wheel(self, event=None):
        """Handles vertical scrolling with the mouse wheel."""
        # self.update_sizes()  # Ensure sizes are up-to-date
        if self.content_height > self.canvas_height:
            scroll_amount = int(-1 * (event.delta / 120))  # Normalize scroll amount
            # print(f"Scrolling vertically: {scroll_amount}")
            self.canvas_widget.yview_scroll(scroll_amount, "units")
        # else:
        #     print("Vertical scrolling not needed.")



    def on_shift_mouse_wheel(self, event=None):
        """Handles horizontal scrolling when Shift is held down."""
        # self.update_sizes()  # Ensure sizes are up-to-date
        if self.content_width > self.canvas_width:
            scroll_amount = int(-1 * (event.delta / 120))  # Normalize scroll amount
            # print(f"Scrolling horizontally: {scroll_amount}")
            self.canvas_widget.xview_scroll(scroll_amount, "units")
        # else:
        #     print("Horizontal scrolling not needed.")


class MCR():
    def __init__(self, mcr_path, ref, res, res_placeholder, isig, isig_placeholder, AP, ANOM, SKIP, TEMPLATE, TEMPLATE_placeholder, progress, *args):
        self.mcr_path=mcr_path
        self.ref=ref
        self.res=res
        self.res_placeholder=res_placeholder
        self.isig=isig
        self.isig_placeholder=isig_placeholder
        self.AP=AP
        self.ANOM=ANOM
        self.SKIP=SKIP
        self.TEMPLATE=TEMPLATE
        self.TEMPLATE_placeholder=TEMPLATE_placeholder
        self.progress = {pr['name']: pr['widget'] for pr in progress}
        self.progress_widget = self.progress.get("self.mcr_progress")
        self.mcr_process=None
        
    def process_run_mcr(self):
        print("accessed process_run_mcr")
        if not self.mcr_process or not self.mcr_process.is_alive():
            self.mcr_process = multiprocessing.Process(target=self.run_mcr)
            self.mcr_process.start()

    def stop_mcr(self):
        print("accessed stop_mcr")
        if self.mcr_process and self.mcr_process.is_alive():
            self.mcr_process.terminate()
            self.mcr_process.join()

    def run_mcr(self):
        print("accessed run_mcr")
        autoproc = "--autoproc" if self.AP == 1 else "" 
        anom = "--anom" if self.ANOM == 1 else ""
        skipdone = "--skipdone" if self.SKIP == 1 else ""
        template = self.TEMPLATE_placeholder if self.TEMPLATE == None else self.TEMPLATE
        highrescut = self.res_placeholder if self.res == None else self.res
        isigcut = self.isig_placeholder if self.isig == None else self.isig

        mycommand = f"{self.mcr_path} --ref {self.ref} --resolution {highrescut} --i_sig_cut {isigcut} {autoproc} {anom} {skipdone} --template_host {template}"

        print(mycommand)
        for i in range(10):
            print(i)
            self.progress_widget.configure(text=i)
            time.sleep(1)

        
class plot_histograms():
    def __init__(self):
        return
    
    def plot_all_ucc(self, directory, filename_pattern, dpi, plots_starting_row):
        if not filename_pattern in self.plots_info_entries or not self.plotted:
            plots_info = ctk.CTkLabel(self.indexing_plots_frame, text=f"Unit cell distribution among datasets with files: {filename_pattern}")
            plots_info.grid(row=plots_starting_row, column=0, columnspan=4, padx=(10,10), pady=(0,0), sticky="w")
            row=plots_starting_row+1
            (_,a,a_mean,a_std,b,b_mean,b_std,c,c_mean,c_std,target_files_counter)=self.collect_sg_cell(directory, filename_pattern)
            self.plot_ucc_histograms(a, "a", row, 0, dpi,filename_pattern)
            self.plot_ucc_histograms(b, "b", row, 1, dpi,filename_pattern)
            self.plot_ucc_histograms(c, "c", row, 2, dpi,filename_pattern)
            # Update the scroll region of the canvas to include the content
            self.indexing_plots_frame.update_idletasks()
            self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
            self.plotted = True
            self.download_plots.configure(state="normal", fg_color=self.default_button_fg_color)
            if not filename_pattern in self.plots_info_entries:
                self.plots_info_entries[filename_pattern] = plots_starting_row
                self.plots_starting_row += 2
        else:
            print("already plotted")
            
    def plot_ucc_histograms(self, ucc, name, row, col, dpi, filename_pattern):
        # Remove existing frame in the specified grid cell
        for widget in self.indexing_plots_frame.grid_slaves(row=row, column=col):
            widget.destroy()
        
        # Create a frame for the plot within the tab
        self.frame = ctk.CTkFrame(self.indexing_plots_frame, width=100)
        self.frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Configure grid row and column weights
        self.indexing_plots_frame.grid_rowconfigure(row, weight=1)
        self.indexing_plots_frame.grid_columnconfigure(col, weight=1)
        self.frame.grid_rowconfigure(row, weight=1)
        self.frame.grid_columnconfigure(col, weight=1)

        try:
            # Create a Matplotlib figure and plot
            fig, ax = plt.subplots(figsize=(3, 3), dpi=dpi)  # Adjust size as needed
            self.fig_entries.append(fig)
            sns.histplot(ucc, bins=100, kde=False, ax=ax)
            ax.axvline(np.min(ucc), color='r', linestyle='dashed', linewidth=1, label=f'Min: {np.min(ucc)}')
            ax.axvline(np.max(ucc), color='g', linestyle='dashed', linewidth=1, label=f'Max: {np.max(ucc)}')
            ax.axvline(np.mean(ucc), color='b', linestyle='dashed', linewidth=1, label=f'Mean: {np.mean(ucc):.2f}')
            ax.axvline(np.mean(ucc) + np.std(ucc), color='y', linestyle='dashed', linewidth=1, label=f'Std Dev: {np.std(ucc):.2f}')
            ax.axvline(np.mean(ucc) - np.std(ucc), color='y', linestyle='dashed', linewidth=1)
            ax.legend(fontsize=7, loc='upper right')
            ax.set_title(f'Unit cell constant {name}', fontsize=9)
            ax.set_xlabel('Value', fontsize=9)
            ax.set_ylabel('Frequency', fontsize=9)
            title=f'Unit cell constant {name}'
            self.fig_details_entries.append([fig,title,filename_pattern])
        finally:
            plt.close('all')  # Ensure all figures are closed
        
        # Create a canvas to display the plot and add it to the frame
        canvas = FigureCanvasTkAgg(fig, master=self.frame)
        canvas_height = self.canvas_plots.winfo_height()-20
        canvas_width = (self.canvas_plots.winfo_width()-60)/3
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.bind("<Button-1>", lambda event, f=fig: self.open_figure_in_new_window(f))

        if self.fit_by == "height":
            canvas_widget.config(width=canvas_height, height=canvas_height)
        else:
            canvas_widget.config(width=canvas_width, height=canvas_width)
        canvas_widget.grid(row=0, column=0, sticky="nsew")  # Ensure proper grid placement
        self.plots_canvases.append(canvas_widget)
        gc.collect()

    def download_plots(self):
        dpi = simpledialog.askinteger("DPI", "Enter DPI (e.g., 100, 200):", minvalue=1, maxvalue=1000)
        if dpi:
            for detail in self.fig_details_entries:
                fig, title, filename_pattern = detail
                fig_name = str(filename_pattern) + "_" + str(title) + "_DPI" + str(dpi) + ".png"
                fig_path = os.path.join(self.dir_entry.get(), fig_name)
                fig.savefig(fig_path, dpi=dpi)
            messagebox.showinfo("Downloaded", f"Figures of UCC collected from datasets with pattern {filename_pattern} were saved in {self.dir_entry.get()}")

    def fitting_plots(self, value):
        if value == 'Fit H':
            self.fitplots_byHeight()
            # self.update_scrollbars()
        elif value == 'Fit W':
            self.fitplots_byWidth()
            # self.update_scrollbars()

    def fitplots_byHeight(self):
        plot_h = round(self.canvas_plots.winfo_height()-80, 0)
        for plot in self.plots_canvases:
            plot.config(width=plot_h, height=plot_h)
        self.indexing_plots_frame.update_idletasks()
        self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
        self.fit_by="height"
    def fitplots_byWidth(self):
        plot_w = round((self.canvas_plots.winfo_width()-80)/3, 0)
        for plot in self.plots_canvases:
            plot.config(width=plot_w, height=plot_w)
        self.indexing_plots_frame.update_idletasks()
        self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
        self.fit_by="width"


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        now = datetime.now()
        formatted_dt = now.strftime("%d %B %Y, %H:%M:%S")
        print(f"\n\n{formatted_dt}\n\n")

        self.title("Genetic Algorithms MX")
        self.geometry(f"{1300}x{580}+{20}+{40}")
        self.placeholder_color = "grey"    
        # configure grid layout (4x4)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0, 1, 2), weight=1)



#                   ██    ██  █████  ██████  ██  █████  ██████  ██      ███████ ███████ 
#                   ██    ██ ██   ██ ██   ██ ██ ██   ██ ██   ██ ██      ██      ██      
#                   ██    ██ ███████ ██████  ██ ███████ ██████  ██      █████   ███████ 
#                    ██  ██  ██   ██ ██   ██ ██ ██   ██ ██   ██ ██      ██           ██ 
#                     ████   ██   ██ ██   ██ ██ ██   ██ ██████  ███████ ███████ ███████ 
                                                          
                                                          
        self.placeholder_entries = []
        self.plots_info_entries = {}
        self.plots_starting_row = 1
        self.ucc_entries = {}
        self.flashing_interval = 0.2
        self.has_run = False
        self.previous_size = self.winfo_width(), self.winfo_height()
        self.plotted = False
        self.plots_canvases = []
        self.fig_entries = []
        self.fit_by="height"
        self.fig_details_entries = []
        self.refs_options = None
        self.refs_hall_of_fame = []
        self.named_frames = []
        self.named_canvases = []
        self.named_scrollable_frames = []
        self.named_scrollable_canvases = []
        self.frames_list = []
        self.frame_bars = []
        self._resize_after = None
        self.selected_ref = ""
        self.buttons = []
        self.best_ref_found = tk.BooleanVar()
        self.best_ref_found.set(False)
        self.new_frame_list = []
        self.new_canvas_list = []
        self.mcr_instance = None
        self.REF = None
        self.disabled_entry_fgcolor = "#A9A9A9"

        


#                     ███████ ██ ██████  ███████ ██████   █████  ██████  
#                     ██      ██ ██   ██ ██      ██   ██ ██   ██ ██   ██ 
#                     ███████ ██ ██   ██ █████   ██████  ███████ ██████  
#                          ██ ██ ██   ██ ██      ██   ██ ██   ██ ██   ██ 
#                     ███████ ██ ██████  ███████ ██████  ██   ██ ██   ██ 
                                                   
                                                   
                                            
                                            
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.named_frames.append(NamedWidget("self.sidebar_frame", self.sidebar_frame))
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="CODGAS GUI", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.sidebar_button_1 = ctk.CTkButton(self.sidebar_frame, text="Documentation", command=self.open_documentation_url)
        self.sidebar_button_1.grid(row=1, column=0, padx=20, pady=10)
        self.sidebar_button_2 = ctk.CTkButton(self.sidebar_frame, text="Copy citation", command=self.copy_citation)
        self.sidebar_button_2.grid(row=2, column=0, padx=20, pady=10)
        self.sidebar_button_4 = ctk.CTkButton(self.sidebar_frame, text="View parameters log", command=self.view_parameters)
        self.sidebar_button_4.grid(row=4, column=0, padx=20, pady=10)

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark"], command=self.change_appearance_mode_event) 
        default_bg_color = self.get_default_bg_color()

        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(10, 10))

        # create tabview
        self.tabview = ctk.CTkTabview(self, width=850, height=560)
        self.tabview.grid(row=0, column=1, padx=(10, 10), pady=(10, 10), sticky="nsew")

        
        
        

        
#                              ██████   █████  ████████  █████  
#                              ██   ██ ██   ██    ██    ██   ██ 
#                              ██   ██ ███████    ██    ███████ 
#                              ██   ██ ██   ██    ██    ██   ██ 
#                              ██████  ██   ██    ██    ██   ██ 


        self.tabview.add("Data")
        for col in range(6):
            self.tabview.tab("Data").grid_columnconfigure(col, weight=0, uniform="a")
        
#######           Data tab           #######
        self.optionmenu_1_label = ctk.CTkLabel(self.tabview.tab("Data"), text="Sub datasets directory:")
        self.optionmenu_1_label.grid(row=0, column=0, padx=0, pady=(10, 0))
        self.browse_button = ctk.CTkButton(self.tabview.tab("Data"), text="Browse", command=self.browse_file)
        self.browse_button.grid(row=0, column=4, padx=20, pady=(20, 20))
        self.dir_placeholder = "Enter directory"
        self.dir_entry = PlaceholderEntry(self.tabview.tab("Data"), placeholder_text=self.dir_placeholder)
        self.placeholder_entries.append([self.dir_entry, self.dir_placeholder])  
        self.dir_entry.grid(row=0, column=1, columnspan=3, padx=(20, 0), pady=(20, 20), sticky="nsew")
        
        
        
# SPACEGROUP        
        self.SG_label = ctk.CTkLabel(self.tabview.tab("Data"), text="SPACEGROUP number:")
        self.SG_label.grid(row=1, column=0, padx=0, pady=(10, 0))        

        self.SG_placeholder = "SG number format"
        self.SG = PlaceholderEntry(self.tabview.tab("Data"), placeholder_text=self.SG_placeholder)
        self.SG.grid(row=1, column=1, columnspan=1, padx=(20, 0), pady=(20, 20), sticky="nsew")
        self.placeholder_entries.append([self.SG, self.SG_placeholder])  
        
        self.SGinfo_button = ctk.CTkButton(self.tabview.tab("Data"), text="SG tables", command=self.SG_INFO, width=80)
        self.SGinfo_button.grid(row=1, column=2, padx=0, pady=(20, 20))


# unit cell a         
        self.UCC_a_label = ctk.CTkLabel(self.tabview.tab("Data"), text="Unit cell a:", width=100)
        self.UCC_a_label.grid(row=2, column=0, padx=0, pady=(10, 0))        
        self.UCC_a_placeholder = "a (Å)"
        self.UCC_a = PlaceholderEntry(self.tabview.tab("Data"), placeholder_text=self.UCC_a_placeholder)   
        self.UCC_a.grid(row=2, column=1, columnspan=1, padx=(0, 0), pady=(20, 20))
        self.placeholder_entries.append([self.UCC_a, self.UCC_a_placeholder])     
        

# unit cell b         
        self.UCC_b_label = ctk.CTkLabel(self.tabview.tab("Data"), text="Unit cell b:", width=100)
        self.UCC_b_label.grid(row=2, column=2, padx=(20,0), pady=(10, 0))        
        self.UCC_b_placeholder = "b (Å)"
        self.UCC_b = PlaceholderEntry(self.tabview.tab("Data"), placeholder_text=self.UCC_b_placeholder)   
        self.UCC_b.grid(row=2, column=3, columnspan=1, padx=(0, 0), pady=(20, 20))
        self.placeholder_entries.append([self.UCC_b, self.UCC_b_placeholder])     
        
        
# unit cell c         
        self.UCC_c_label = ctk.CTkLabel(self.tabview.tab("Data"), text="Unit cell c:", width=100)
        self.UCC_c_label.grid(row=2, column=4, padx=(20,0), pady=(10, 0))        
        self.UCC_c_placeholder = "c (Å)"
        self.UCC_c = PlaceholderEntry(self.tabview.tab("Data"), placeholder_text=self.UCC_c_placeholder)   
        self.UCC_c.grid(row=2, column=5, columnspan=1, padx=(0, 20), pady=(20, 20))
        self.placeholder_entries.append([self.UCC_c, self.UCC_c_placeholder])
        
        
        self.info_ucc = ctk.CTkLabel(self.tabview.tab("Data"), text="Information gathered from datasets found in the selected directory")
        self.info_ucc.grid(row=3, column=0, columnspan=3, padx=(20,0), pady=(40,0), sticky="w")  
        self.update_with_mean_button = ctk.CTkButton(self.tabview.tab("Data"), state="disabled", fg_color="grey", text="Update data above with the mean from below", command=lambda: self.update_UCC())
        self.update_with_mean_button.grid(row=3, column=3, columnspan=2, padx=(20,0), pady=(40,0))
        self.buttons.append(self.update_with_mean_button)
        
        self.label_pattern_counter = ctk.CTkLabel(self.tabview.tab("Data"), text="")
        self.label_pattern_counter.grid(row=4, column=0, columnspan=3, padx=(20,0), pady=(0, 10), sticky="w")      
        grid_X_origin_labels_ucc_gathered_info = 5
        grid_Y_origin_labels_ucc_gathered_info = 0
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info, grid_Y_origin_labels_ucc_gathered_info , "min(a)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+1, grid_Y_origin_labels_ucc_gathered_info , "max(a)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+2, grid_Y_origin_labels_ucc_gathered_info , "mean(a)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+3, grid_Y_origin_labels_ucc_gathered_info , "std(a)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info, grid_Y_origin_labels_ucc_gathered_info+2 , "min(b)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+1, grid_Y_origin_labels_ucc_gathered_info+2 , "max(b)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+2, grid_Y_origin_labels_ucc_gathered_info+2 , "mean(b)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+3, grid_Y_origin_labels_ucc_gathered_info+2 , "std(b)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info, grid_Y_origin_labels_ucc_gathered_info+4 , "min(c)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+1, grid_Y_origin_labels_ucc_gathered_info+4 , "max(c)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+2, grid_Y_origin_labels_ucc_gathered_info+4 , "mean(c)=")
        self.add_labels_ucc_gathered_info(grid_X_origin_labels_ucc_gathered_info+3, grid_Y_origin_labels_ucc_gathered_info+4 , "std(c)=")




#                     ██ ███    ██ ██████  ███████ ██   ██ ██ ███    ██  ██████  
#                     ██ ████   ██ ██   ██ ██       ██ ██  ██ ████   ██ ██       
#                     ██ ██ ██  ██ ██   ██ █████     ███   ██ ██ ██  ██ ██   ███ 
#                     ██ ██  ██ ██ ██   ██ ██       ██ ██  ██ ██  ██ ██ ██    ██ 
#                     ██ ██   ████ ██████  ███████ ██   ██ ██ ██   ████  ██████  
                                                           
                                                           
                                                 
                                                 
        self.tabview.add("Indexing")

        # Create a frame inside the canvas to hold the content
        self.indexing_content_frame = ctk.CTkFrame(self.tabview.tab("Indexing"), bg_color=default_bg_color, border_width=0,corner_radius=0)
        self.named_frames.append(NamedWidget("self.indexing_content_frame", self.indexing_content_frame))
        self.indexing_content_frame.grid(row=0, column=0, sticky="nsew")


        # Create a Canvas to use with the scrollbars
        self.canvas_plots = ctk.CTkCanvas(self.indexing_content_frame, bg=default_bg_color, borderwidth=0, relief="flat", highlightthickness=0, width=400, height=400)
        self.named_canvases.append(NamedWidget("self.canvas_plots", self.canvas_plots))
        self.canvas_plots.grid(row=2, column=0, columnspan=6, sticky="nsew")

        
        # Create a frame inside the canvas to hold the plots
        self.indexing_plots_frame = ctk.CTkFrame(self.canvas_plots, bg_color=default_bg_color, border_width=0, corner_radius=0, height=300)
        self.named_frames.append(NamedWidget("self.indexing_plots_frame", self.indexing_plots_frame))
        self.canvas_plots.create_window((0, 0), window=self.indexing_plots_frame, anchor="nw")
        
        self.canvas_plots.bind('<Configure>', lambda event: self.on_canvas_configure(event, self.indexing_content_frame))
    
    
        self.new_frame_list.append({"name": "self.indexing_plots_frame", "widget": self.indexing_plots_frame})
        self.new_canvas_list.append({"name": "self.canvas_plots", "widget": self.canvas_plots})
        
        # Add vertical and horizontal scrollbars
        self.indexing_v_scrollbar = ManagedCTkScrollbar(
            parent=self.tabview.tab("Indexing"),
            orientation="vertical", 
            command=self.canvas_plots.yview,
            frames_list=self.new_frame_list,
            canvases_list=self.new_canvas_list,
            frames_names=["self.indexing_plots_frame"],
            canvas_name="self.canvas_plots"
            )
        self.indexing_v_scrollbar.grid(row=0, column=1, sticky="ns")
    
        self.indexing_h_scrollbar = ManagedCTkScrollbar(
            parent=self.tabview.tab("Indexing"),
            orientation="horizontal", 
            command=self.canvas_plots.xview,
            frames_list=self.new_frame_list,
            canvases_list=self.new_canvas_list,
            frames_names=["self.indexing_plots_frame"],
            canvas_name="self.canvas_plots"
            )
        self.indexing_h_scrollbar.grid(row=2, column=0, sticky="ew")

        # Configure scrollbars
        self.canvas_plots.configure(yscrollcommand=self.indexing_v_scrollbar.set, xscrollcommand=self.indexing_h_scrollbar.set)
        

        self.named_scrollable_frames.append(NamedWidget("self.indexing_plots_frame", self.indexing_plots_frame))
        self.frames_list.append("self.indexing_plots_frame")
        self.named_scrollable_canvases.append(NamedWidget("self.canvas_plots", self.canvas_plots))
        self.frame_bars.append(NamedScrollbars("self.canvas_plots", self.indexing_h_scrollbar, self.indexing_v_scrollbar))


        self.filename = ctk.CTkLabel(self.indexing_content_frame, text="File name pattern")
        self.filename.grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        self.combo_box = ctk.CTkComboBox(self.indexing_content_frame, values=["CORRECT.LP", "REPROC.HKL", "XDS_ASCII.HKL", "other"], command=self.on_combo_box_select)
        self.combo_box.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self.filename_placeholder = "enter a specific file name pattern"
        
        self.filename_entry = PlaceholderEntry(
            self.indexing_content_frame, 
            placeholder_text=self.filename_placeholder, 
            callback=self.other_pattern, 
            state="disabled", 
            fg_color=self.disabled_entry_fgcolor, 
            width=200)   
        
        self.filename_entry.grid(row=0, column=2, padx=4, pady=4, sticky="we")
        self.placeholder_entries.append([self.filename_entry, self.filename_placeholder])
        self.combo_box.bind("<<ComboboxSelected>>", self.on_combo_box_select)
        self.filename_pattern = self.combo_box.get()

        self.ucc_sg_calc = ctk.CTkButton(self.indexing_content_frame, text="insert in 'Data'", command=lambda: self.insert_ucc_gathered_update_fgcolor(self.dir_entry.get(),self.filename_pattern), width=60)
        self.ucc_sg_calc.grid(row=0, column=3, padx=4, pady=4, sticky="ew")
        self.dpi=100
        self.plot_ucc = ctk.CTkButton(self.indexing_content_frame, text="plot", command=lambda: self.plot_all_ucc(self.dir_entry.get(),self.filename_pattern, self.dpi, self.plots_starting_row), width=60)
        self.plot_ucc.grid(row=1, column=3, padx=4, pady=4, sticky="ew")
        
        self.download_plots = ctk.CTkButton(self.indexing_content_frame, text="Download all", command=self.download_plots, width=60, state="disabled", fg_color="grey")
        self.download_plots.grid(row=0, column=4, padx=4, pady=4, sticky="ew")
        self.SG_plots = ctk.CTkButton(self.indexing_content_frame, text="Show SG", command=lambda: self.plot_SG_pie_chart(self.dir_entry.get(), self.filename_pattern), width=30)
        self.SG_plots.grid(row=0, column=5, padx=(4,40), pady=4, sticky="ew")
        
        self.DPI = ctk.CTkLabel(self.indexing_content_frame, text="DPI")
        self.DPI.grid(row=1, column=0, padx=4, pady=4)
        self.dpi_box = ctk.CTkComboBox(self.indexing_content_frame, values=["100", "150", "200", "50"], command=self.update_dpi_value, width=80)
        self.dpi_box.grid(row=1, column=1, padx=4, pady=4)

        self.fit = ctk.CTkSegmentedButton(self.indexing_content_frame, values=['Fit H', 'Fit W'], command=self.fitting_plots)
        self.fit.grid(row=1, column=4, padx=4, pady=4)
        self.fit.set(value='Fit H')

        self.bind("<Configure>", self.on_resize)
        self.canvas_plots.config(scrollregion=self.indexing_plots_frame.bbox("all"))
        
        self.current_mode = ctk.get_appearance_mode()
        self.tabview.tab("Indexing").update_idletasks()
        # self.tabview.set("ReIndexing")
        

        
        
        
#                 ██████  ███████     ██ ███    ██ ██████  ███████ ██   ██ ██ ███    ██  ██████  
#                 ██   ██ ██          ██ ████   ██ ██   ██ ██       ██ ██  ██ ████   ██ ██       
#                 ██████  █████       ██ ██ ██  ██ ██   ██ █████     ███   ██ ██ ██  ██ ██   ███ 
#                 ██   ██ ██          ██ ██  ██ ██ ██   ██ ██       ██ ██  ██ ██  ██ ██ ██    ██ 
#                 ██   ██ ███████     ██ ██   ████ ██████  ███████ ██   ██ ██ ██   ████  ██████  
                                                                                            
                                                                               
                                                                                                                      
        self.tabview.add("ReIndexing")        



        # Create a Canvas to use with the scrollbars
        self.Reindexing_canvas = ctk.CTkCanvas(self.tabview.tab("ReIndexing"), bg=default_bg_color, borderwidth=0, relief="flat", highlightthickness=0)
        self.named_canvases.append(NamedWidget("self.Reindexing_canvas", self.Reindexing_canvas))
        self.Reindexing_canvas.grid(row=0, column=0, sticky="nsew")

        # Create a frame inside the canvas to hold the content
        self.Reindexing_content_frame = ctk.CTkFrame(self.Reindexing_canvas, bg_color=default_bg_color, border_width=1, corner_radius=5)
        self.named_frames.append(NamedWidget("self.Reindexing_content_frame", self.Reindexing_content_frame))
        self.reindex_canvas_frame1 = self.Reindexing_canvas.create_window((0, 0), window=self.Reindexing_content_frame, anchor="nw")
        # Ensure the canvas expands with the window
        self.Reindexing_canvas.bind('<Configure>', lambda event: self.on_canvas_configure(event, self.Reindexing_content_frame))

        
        self.named_scrollable_frames.append(NamedWidget("self.Reindexing_content_frame", self.Reindexing_content_frame))
        self.frames_list.append("self.Reindexing_content_frame")
        self.named_scrollable_canvases.append(NamedWidget("self.Reindexing_canvas", self.Reindexing_canvas))
        
        self.new_frame_list.append({"name": "self.Reindexing_content_frame", "widget": self.Reindexing_content_frame})
        self.new_canvas_list.append({"name": "self.Reindexing_canvas", "widget": self.Reindexing_canvas})
        



        # self.tabview.set("Indexing")
        

#######           Reindexing tab           #######
        self.reindexing_intro = ctk.CTkLabel(self.Reindexing_content_frame, text=
                                             "Reindexing datasets with a common reference HKL file, helps ensuring a consistent indexing along all of them.\nThis XDS_ASCII.HKL will be chosen based on the stats from the corresponding CORRECT.LP.                                 ", anchor="w")
        self.reindexing_intro.grid(row=0, column=0, columnspan=6, padx=10, pady=10, stick="w")
        self.mcr_path_label = ctk.CTkLabel(
            self.Reindexing_content_frame, 
            text="Script path:")
        self.mcr_path_label.grid(row=1, column=0, padx=10, pady=10, stick="w")
        # self.mcr_path = ctk.CTkEntry(self.Reindexing_content_frame)
        self.mcr_path_placeholder = "Enter mesh_collect_reproc.perl script path"
        self.mcr_path = PlaceholderEntry(
            self.Reindexing_content_frame, 
            placeholder_text=self.mcr_path_placeholder)
        self.placeholder_entries.append([self.mcr_path, self.mcr_path_placeholder])  
        self.mcr_path.grid(row=1, column=1, columnspan=3, padx=10, pady=10, sticky="nsew")
        self.mcr_browse_button = ctk.CTkButton(
            self.Reindexing_content_frame, 
            text="Browse", 
            width=100, 
            command=self.mcr_browse_path)
        self.mcr_browse_button.grid(row=1, column=4, padx=10, pady=10)
        self.default_button_fg_color = self.mcr_browse_button.cget("fg_color")
        self.ref_label = ctk.CTkLabel(
            self.Reindexing_content_frame, 
            text="Finding Reference dataset:")
        self.ref_label.grid(row=2, column=0, columnspan=1, padx=10, pady=10, sticky="w")

        self.segment_buttons = []
        self.find_ref_button = ctk.CTkSegmentedButton(
            self.Reindexing_content_frame, 
            values=["Auto", "Auto-guided", "Manual"], 
            command=self.find_ref_button_function)
        self.find_ref_button.grid(row=2, column=1, padx=10, pady=10)
        self.previous_selection_find_ref = None

        self.best_ref_label = ctk.CTkLabel(self.Reindexing_content_frame, text="Best REF dataset is:")
        self.best_ref_label.grid(row=3, column=0, columnspan=1, sticky="w", padx=10, pady=10)
        self.set_ref_button = ctk.CTkButton(
            self.Reindexing_content_frame, 
            state="disabled", 
            text="Set as REF", 
            width=100, 
            command=self.set_ref, 
            fg_color="gray")
        self.set_ref_button.grid(row=3, column=4, padx=10, pady=10)
        self.buttons.append(self.set_ref_button)
        # Load the green check mark image
        self.check_mark_image = Image.open("./green_check.png")
        self.check_mark_image = self.check_mark_image.resize((100, 100))  # Resize to 50x50 pixels
        # Ensure the image has an alpha channel
        if self.check_mark_image.mode != 'RGBA':
            self.check_mark_image = self.check_mark_image.convert('RGBA')
        self.check_mark_photo = ctk.CTkImage(light_image=self.check_mark_image, dark_image=self.check_mark_image)


        def toggle_set_best_ref_button(bestref):
            if bestref != "":
                self.selected_ref = bestref
                self.best_ref_found.set(True)
            else:
                self.best_ref_found.set(False)
            return

        
        self.best_ref_placeholder = "Reference dataset will appear here"
        self.best_ref = PlaceholderEntry(
            self.Reindexing_content_frame, 
            placeholder_text=self.best_ref_placeholder, 
            callback=toggle_set_best_ref_button, 
            state="disabled", 
            fg_color=self.disabled_entry_fgcolor)
        # self.placeholder_entries.append([self.best_ref, self.best_ref_placeholder])
        self.best_ref.grid(row=3, column=1, columnspan=3, padx=10, pady=10, sticky="nsew")


        
        self.best_ref_found.trace_add("write", self.on_bestref_change_enable_set)
        
        self.ref_option_table = ctk.CTkLabel(self.Reindexing_content_frame, text="")
        self.ref_option_table.grid(row=5, column=0, columnspan=6, padx=(50,0), pady=(0,10), sticky='nsw')
        
        self.correctlp_header = ctk.CTkLabel(self.Reindexing_content_frame, text="", anchor="w")
        self.correctlp_header.grid(row=4, column=0, columnspan=6, padx=(50,0), pady=(10,0), sticky='nsw')
        self.Reindexing_content_frame.grid_rowconfigure(4, weight=1)
        self.Reindexing_content_frame.grid_rowconfigure(5, weight=1)
        self.Reindexing_canvas.config(scrollregion=self.Reindexing_content_frame.bbox("all"))

        self.configure_grids(self.Reindexing_content_frame)
        self.configure_grids(self.indexing_content_frame)
        
        self.tabview.tab("ReIndexing").update_idletasks()

        for col in range(5):
            self.Reindexing_content_frame.grid_columnconfigure(col, weight=1, uniform="a")


# frame 2
        self.mesh_collect_frame = ctk.CTkFrame(self.Reindexing_canvas, bg_color=default_bg_color, border_width=1, corner_radius=5)
        self.named_frames.append(NamedWidget("self.mesh_collect_frame", self.mesh_collect_frame))
        self.reindex_canvas_frame2 = self.Reindexing_canvas.create_window((0, 0), window=self.mesh_collect_frame, anchor="nw")
        self.new_frame_list.append({"name": "self.mesh_collect_frame", "widget": self.mesh_collect_frame})

        def update_layout(event=None):
            # Get the current bounding box of frame1
            frame1_bbox = self.Reindexing_canvas.bbox(self.reindex_canvas_frame1)
            
            # Update the position of frame2 based on the height of frame1
            self.Reindexing_canvas.coords(self.reindex_canvas_frame2, 0, frame1_bbox[3] + 20)  # 20 pixels padding
            
            # Update the scroll region of the canvas to include both frames
            self.Reindexing_canvas.configure(scrollregion=self.Reindexing_canvas.bbox("all"))

        self.Reindexing_content_frame.bind("<Configure>", update_layout)
        update_layout()

        self.mcr_run_label = ctk.CTkLabel(self.mesh_collect_frame, text="Reprocess datasets")
        self.mcr_run_label.grid(row=0, column=0, padx=10, pady=4, sticky="nsew")

        self.highREScut = ctk.CTkLabel(self.mesh_collect_frame, text="High RES cutoff")
        self.highREScut.grid(row=1, column=0, padx=(10,30), pady=4, sticky="w")
        self.highREScut_val_placeholder = "1.4"
        self.highREScut_val = PlaceholderEntry(self.mesh_collect_frame, placeholder_text=self.highREScut_val_placeholder, width=50)
        self.highREScut_val.grid(row=1, column=1, columnspan=1, padx=(0,30), pady=4, sticky="w")
        self.placeholder_entries.append([self.highREScut_val, self.highREScut_val_placeholder])  

        self.Isig_cut = ctk.CTkLabel(self.mesh_collect_frame, text="ISIG cutoff")
        self.Isig_cut.grid(row=2, column=0, padx=(10,30), pady=4, sticky="w")
        self.Isig_cut_val_placeholder = "1"
        self.Isig_cut_val = PlaceholderEntry(self.mesh_collect_frame, placeholder_text=self.Isig_cut_val_placeholder, width=50)
        self.Isig_cut_val.grid(row=2, column=1, columnspan=1, padx=(0,30), pady=4, sticky="w")
        self.placeholder_entries.append([self.Isig_cut_val, self.Isig_cut_val_placeholder])  
        
        self.template_host = ctk.CTkLabel(self.mesh_collect_frame, text="Template host")
        self.template_host.grid(row=3, column=0, padx=(10,30), pady=4, sticky="w")
        self.template_host_val_placeholder = "id232control"
        self.template_host_val = PlaceholderEntry(self.mesh_collect_frame, placeholder_text=self.template_host_val_placeholder)
        self.template_host_val.grid(row=3, column=1, columnspan=1, padx=(0,30), pady=4, sticky="w")
        self.placeholder_entries.append([self.template_host_val, self.template_host_val_placeholder])  

        self.autoproc = ctk.CTkSwitch(master=self.mesh_collect_frame, text="AutoPROC")
        self.autoproc.grid(row=1, column=2, padx=10, pady=4, sticky="ew")

        self.anom = ctk.CTkSwitch(master=self.mesh_collect_frame, text="Friedel's Law")
        self.anom.grid(row=2, column=2, padx=10, pady=4, sticky="ew")
        
        self.skipdone = ctk.CTkSwitch(master=self.mesh_collect_frame, text="Skip reprocessed")
        self.skipdone.grid(row=3, column=2, padx=10, pady=4, sticky="ew")

        for col in range(4):
            self.mesh_collect_frame.grid_columnconfigure(col, weight=1, uniform="a")

# columnconfigure(0, weight = 1, uniform="a")

        # def printvalues():
        #     print("self.highREScut_val: ", self.highREScut_val.get())
        #     print("self.Isig_cut_val: ", self.Isig_cut_val.get())
        #     print("self.template_host_val: ", self.template_host_val.get())
        #     print("self.autoproc: ", self.autoproc.get())
        #     print("self.anom: ", self.anom.get())
        #     print("self.skipdone: ", self.skipdone.get())

        self.slurm_check = ctk.CTkCheckBox(master=self.mesh_collect_frame, text="Slurm", onvalue="on", offvalue="off")
        self.slurm_check.grid(row=3, column=4, padx=10, pady=4)

        self.run_mcr_button = ctk.CTkButton(self.mesh_collect_frame, text="RUN", fg_color="green", hover_color="darkgreen", command=self.run_MCR, width=100)
        self.run_mcr_button.grid(row=1, column=4, padx=10, pady=4)

        self.stop_mcr_button = ctk.CTkButton(self.mesh_collect_frame, text="STOP", fg_color="red", hover_color="darkred", command=self.stop_MCR, width=100)
        self.stop_mcr_button.grid(row=2, column=4, padx=10, pady=(4, 10))

        self.mcr_progress = ctk.CTkLabel(self.mesh_collect_frame, text="")
        self.mcr_progress.grid(row=4, column=0, padx=10, pady=10)



#scrollbars
        self.reindexing_h_scrollbar = ManagedCTkScrollbar(
            parent=self.tabview.tab("ReIndexing"),
            orientation="horizontal",
            command=self.Reindexing_canvas.xview,
            frames_list=self.new_frame_list,
            canvases_list=self.new_canvas_list,
            frames_names=["self.Reindexing_content_frame", "self.mesh_collect_frame"],
            canvas_name="self.Reindexing_canvas"
        )
        self.reindexing_h_scrollbar.grid(row=1, column=0, sticky="ew")


        self.reindexing_v_scrollbar = ManagedCTkScrollbar(
            parent=self.tabview.tab("ReIndexing"),
            orientation="vertical",
            command=self.Reindexing_canvas.yview,
            frames_list=self.new_frame_list,
            canvases_list=self.new_canvas_list,
            frames_names=["self.Reindexing_content_frame","self.mesh_collect_frame"],
            canvas_name="self.Reindexing_canvas"
        )
        self.reindexing_v_scrollbar.grid(row=0, column=1, sticky="ns")


#######           Processing tab           #######
        self.tabview.add("Processing")
        self.tabview.add("Analysing")

#######           Analysing tab            #######



        
#          ██████  ██████  ███    ██ ███████ ██  ██████  ██    ██ ██████  ███████ 
#         ██      ██    ██ ████   ██ ██      ██ ██       ██    ██ ██   ██ ██      
#         ██      ██    ██ ██ ██  ██ █████   ██ ██   ███ ██    ██ ██████  █████   
#         ██      ██    ██ ██  ██ ██ ██      ██ ██    ██ ██    ██ ██   ██ ██      
#          ██████  ██████  ██   ████ ██      ██  ██████   ██████  ██   ██ ███████ 
                                                                        
                                                                    
        # Configure the grid of the parent tab
        self.tabview.grid_rowconfigure(0, weight=1)
        self.tabview.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)  # Make the row with the Tabview expand vertically
        self.grid_columnconfigure(1, weight=1)  # Make the column with the Tabview expand horizontally
        
        # Update the scroll region of the canvas to include the content
        self.indexing_plots_frame.update_idletasks()
        self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
        self.update_canvas_size(self.canvas_plots,self.indexing_plots_frame)
        
        # Configure weight for grid columns and rows
        self.tabview.tab("Indexing").grid_rowconfigure(0, weight=1)
        self.tabview.tab("Indexing").grid_columnconfigure(0, weight=1)
        self.indexing_content_frame.grid_rowconfigure(0, weight=0)
        self.indexing_content_frame.grid_rowconfigure(1, weight=0)
        for col in range(6):
            self.indexing_content_frame.grid_columnconfigure(col, weight=1)
        self.indexing_content_frame.grid_rowconfigure(2, weight=1)

        # Configure grid weights
        self.tabview.tab("ReIndexing").grid_rowconfigure(0, weight=1)
        self.tabview.tab("ReIndexing").grid_columnconfigure(0, weight=1)
        self.Reindexing_content_frame.grid_rowconfigure(0, weight=1)
        self.Reindexing_content_frame.grid_columnconfigure(0, weight=1)

        # Configure weight for grid columns and rows
        self.Reindexing_canvas.grid_rowconfigure(0, weight=1)
        self.Reindexing_canvas.grid_columnconfigure(0, weight=1)
        self.Reindexing_content_frame.update_idletasks()
        self.Reindexing_canvas.update_idletasks()
        self.update_canvas_size(self.Reindexing_canvas,self.Reindexing_content_frame)
        

        # Bind the configure event to the resize callback
        self.bind("<Configure>", self.on_resize)        
        
        
        for button in self.buttons:
            if button.cget("state") == "normal":
                button.bind("<ButtonPress-1>", self.on_button_press)  # Button press event
                button.bind("<ButtonRelease-1>", self.on_button_release)  # Button release event

        
        print(f"Memory usage: {self.memory_usage() / (1024 * 1024):.2f} MB")

        # self.bind('<Configure>', ManagedCTkScrollbar.update_scrollbar_visibility)

        self.bind("<Alt-q>", lambda event: self.quit())

            

#                ███████ ██    ██ ███    ██  ██████ ████████ ██  ██████  ███    ██ ███████ 
#                ██      ██    ██ ████   ██ ██         ██    ██ ██    ██ ████   ██ ██      
#                █████   ██    ██ ██ ██  ██ ██         ██    ██ ██    ██ ██ ██  ██ ███████ 
#                ██      ██    ██ ██  ██ ██ ██         ██    ██ ██    ██ ██  ██ ██      ██ 
#                ██       ██████  ██   ████  ██████    ██    ██  ██████  ██   ████ ███████ 

 
# MCR
    def run_MCR(self):
        widget_dict=[]
        widget_dict.append({"name": "self.mcr_progress", "widget": self.mcr_progress})
        if self.REF:
            self.mcr_instance = MCR(self.mcr_path.get_value(),
                        self.selected_ref,
                        self.highREScut_val.get_value(),
                        self.highREScut_val_placeholder,
                        self.Isig_cut_val.get_value(),
                        self.Isig_cut_val_placeholder,
                        self.autoproc.get(),
                        self.anom.get(),
                        self.skipdone.get(),
                        self.template_host_val.get_value(),
                        self.template_host_val_placeholder,
                        widget_dict
                        )
            self.mcr_instance.process_run_mcr()
        else:
            messagebox.showerror("Error", f"You have to set the selected dataset as a reference first!")
        
        # if state == "start":
        #     print("start button is clicked")
        #     instance.process_run_mcr()
        # elif state == "stop":
        #     print("stop button is clicked")
        #     instance.stop_mcr
        
    def stop_MCR(self):
        if self.mcr_instance:
            # Stop the MCR process
            self.mcr_instance.stop_mcr()

        
        
        
        # if not self.mcr_process or not self.mcr_process.is_alive():
        #     self.mcr_process = multiprocessing.Process(target=self.run_mcr)
        #     self.mcr_process.start()


# UCC and SG values

    def update_UCC(self):
        self.UCC_a.set_value(self.a_mean)
        self.UCC_b.set_value(self.b_mean)
        self.UCC_c.set_value(self.c_mean)

    def add_labels_ucc_gathered_info(self, row, col, text):
        labelX = ctk.CTkLabel(self.tabview.tab("Data"), text=text, width=60)
        labelX.grid(row=row, column=col, padx=10, pady=4, sticky="e")        
        valueX = ctk.CTkEntry(self.tabview.tab("Data"), state="disabled", width=70, fg_color=self.disabled_entry_fgcolor)
        valueX.grid(row=row, column=(col+1), padx=10, pady=0, sticky="w")
        self.ucc_entries[text] = valueX

    def insert_ucc_sg_mean_std_indata(self, directory, filename_pattern):
        (_,a,a_mean,a_std,b,b_mean,b_std,c,c_mean,c_std,target_files_counter)=self.collect_sg_cell(directory, filename_pattern)
        self.a_mean = a_mean
        self.b_mean = b_mean
        self.c_mean = c_mean
        a_min = str(np.min(a))
        a_max = str(np.max(a))
        b_min = str(np.min(b))
        b_max = str(np.max(b))
        c_min = str(np.min(c))
        c_max = str(np.max(c))
        self.update_ucc_gathered_value("min(a)=", a_min)
        self.update_ucc_gathered_value("max(a)=", a_max)
        self.update_ucc_gathered_value("mean(a)=", a_mean)
        self.update_ucc_gathered_value("std(a)=", a_std)
        self.update_ucc_gathered_value("min(b)=", b_min)
        self.update_ucc_gathered_value("max(b)=", b_max)
        self.update_ucc_gathered_value("mean(b)=", b_mean)
        self.update_ucc_gathered_value("std(b)=", b_std)
        self.update_ucc_gathered_value("min(c)=", c_min)
        self.update_ucc_gathered_value("max(c)=", c_max)
        self.update_ucc_gathered_value("mean(c)=", c_mean)
        self.update_ucc_gathered_value("std(c)=", c_std)

        self.tabview.set("Data")
        for _, ucc_entry in self.ucc_entries.items():
            ucc_entry.configure(fg_color="lightgreen")
        self.label_pattern_counter.configure(text=f"Found {target_files_counter} datasets with pattern name: {filename_pattern}")
        
    def reset_ucc_entries_gathered(self):
        self.flashes = 4
        self.current_flash = 0
        self.flash_entries()

    def flash_entries(self):
        # if not self.has_run:
        color = self.logo_label.cget("text_color")
        strcolor = color if isinstance(color, str) else color[0]
        self.label_original_color = strcolor if ctk.get_appearance_mode() == "Light" else "white"

        if self.current_flash < self.flashes:
            # Toggle the color
            new_color = "lightgreen" if self.current_flash % 2 == 0 else self.disabled_entry_fgcolor 
            label_color = "red" if self.current_flash % 2 == 0 else self.label_original_color
            for _, ucc_entry in self.ucc_entries.items():
                ucc_entry.configure(fg_color=new_color)
            self.label_pattern_counter.configure(text_color=label_color)
            
            # Schedule the next flash
            self.current_flash += 1
            self.after(int(self.flashing_interval*1000), self.flash_entries)
        else:
            # Reset to default color after flashing
            for _, ucc_entry in self.ucc_entries.items():
                ucc_entry.configure(fg_color=self.disabled_entry_fgcolor)
            self.label_pattern_counter.configure(text_color=self.label_original_color)
            
    def insert_ucc_gathered_update_fgcolor(self, directory, filename_pattern):
        self.insert_ucc_sg_mean_std_indata(directory, filename_pattern)
        self.after(int(self.flashing_interval*1000), self.reset_ucc_entries_gathered)
        self.update_with_mean_button.configure(state="normal", fg_color=self.default_button_fg_color)

    def update_ucc_gathered_value(self, ucc_info, ucc_value):
        if ucc_info in self.ucc_entries:
            ucc_entry = self.ucc_entries[ucc_info]
            ucc_entry.configure(state="normal")
            ucc_entry.delete(0, "end")
            ucc_entry.insert(0, ucc_value)
            ucc_entry.configure(state="readonly", text_color="black")


# miscellaneous 

 
    def configure_grids(self, holder):
        self.holder = holder
        widget_list = self.holder.winfo_children()
        maximum_rows=0
        row_nb=0
        for widget in widget_list:
            # print(widget,": ", widget.grid_info(),"\n")
            row_nb = widget.grid_info().get('row', None)
            if row_nb >= maximum_rows:
                maximum_rows = row_nb
        for col in range(maximum_rows+1):
            self.holder.grid_rowconfigure(col, weight=1)

    def on_button_press(self, event):
        button = event.widget
        while button and not isinstance(button, ctk.CTkButton):
            button = button.master
        if button.cget("state")=="normal":
            button.configure(border_width=3)  # Increase border width to simulate pressing

    def on_button_release(self, event):
        button = event.widget
        while button and not isinstance(button, ctk.CTkButton):
            button = button.master
        if button.cget("state")=="normal":
            button.configure(border_width=0)  # Restore original border width
    
    def print_size(self, target, target_name):
        self.update_idletasks()
        # Query sizes
        width = target.winfo_width()
        height = target.winfo_height()
        print(f"Size of {target_name}: {width}x{height}")

    def update_buttons_colors(self, pressed_button):
        for button in self.reindexing_buttons:
            if button == pressed_button:
                button.configure(fg_color="green", hover_color="darkgreen")
            else:
                button.configure(fg_color="#1F6AA5", hover_color="#144870")

    def update_canvas_size(self, canvas, frame):
        # Update the canvas to ensure all items are rendered
        canvas.update_idletasks()
        frame.update_idletasks()

        # Get the bounding box of all items on the canvas
        bbox = frame.bbox("all")
        
        if bbox:
            # bbox returns (x1, y1, x2, y2)
            box_height = bbox[3] - bbox[1]
            box_width = bbox[2] - bbox[0]
        else:
            # If no items, default height
            box_height = 100
            box_width = 400
            
        # Update the canvas height
        canvas.config(height=box_height, width=box_width)
        frame.configure(height=box_height, width=box_width)
        

        # Adjust the scrolling region to match the content height
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_configure(self, event, frame):
        # Resize the specified frame to match the canvas size
        canvas_width = event.width
        canvas_height = event.height
        frame.configure(width=canvas_width, height=canvas_height)
        
    def on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.Reindexing_canvas.configure(scrollregion=self.Reindexing_canvas.bbox("all"))

    def update_font_color(self):
        # Get the current appearance mode
        mode = ctk.get_appearance_mode()
        # Iterate through all entries and update their font color if they don't show the placeholder
        for entry, place in self.placeholder_entries:
            # if entry.get() != placeholder:
            print(place, " : ", entry.get_value()) 
            textcolor = "grey" if entry.get_value()==None else ("black" if mode == "Light" else "white")
            entry.configure(text_color=textcolor)
            if entry.cget("state") == "readonly":
                fgcolor = "gray86"
                entry.configure(fg_color=fgcolor)
            elif entry.cget("state") == "disabled":
                fgcolor = "gray70"
                entry.configure(fg_color=fgcolor)
            else:
                fgcolor = "white" if mode == "Light" else "gray17" 
                entry.configure(fg_color=fgcolor)
                
        textcolor = "black" if mode == "Light" else "white"
        self.label_pattern_counter.configure(text_color=textcolor)

    def change_appearance_mode_event(self, new_mode):
        ctk.set_appearance_mode(new_mode)
        self.update_font_color()
        self.on_appearance_mode_change_canvas_bg(None, new_mode)
        
    def on_appearance_mode_change(self, event):
        for entry, _ in self.placeholder_entries:
            self.update_font_color()

    def on_appearance_mode_change_canvas_bg(self, event, new_mode):
        color = "gray86" if new_mode == "Light" else "gray17"
        for named_widget in self.named_frames:
            # print(f"Updating {named_widget.name}: {named_widget.widget}")
            if isinstance(named_widget.widget, ctk.CTkFrame):
                try:
                    named_widget.widget.configure(bg_color=color)  # Access the widget for configuration
                    named_widget.widget.update_idletasks()  # update the widget
                    # print(f"{named_widget.name} updated successfully.")
                except Exception as e:
                    print(f"Error configuring {named_widget.name}: {e}")
        for named_widget in self.named_canvases:
            # print(f"Updating {named_widget.name}: {named_widget.widget}")
            if isinstance(named_widget.widget, ctk.CTkCanvas):
                try:
                    named_widget.widget.configure(bg=color)  # Access the widget for configuration
                    named_widget.widget.update_idletasks()  # update the widget
                    # print(f"{named_widget.name} updated successfully.")
                except Exception as e:
                    print(f"Error configuring {named_widget.name}: {e}")

    def is_scrollable_frame(self, frame):
        frame.update_idletasks()  # Ensure layout is updated
        content_height = frame.winfo_reqheight()  # Height of the content
        print(f"content height: {content_height}")
        visible_height = frame.winfo_height()  # Height of the visible area
        print(f"visible height: {visible_height}")
        if content_height > visible_height:
            return True
        else:
            return False


# finding reference
    def on_bestref_change_enable_set(self, *args):
        if self.best_ref_found.get():
            if self.best_ref_found.get():
                self.set_ref_button.configure(state=ctk.NORMAL, fg_color= self.default_button_fg_color)
            else:
                self.set_ref_button.configure(state=ctk.DISABLED, fg_color= "gray")
            
    def set_ref(self):
        print("set ref button pressed")
        if self.best_ref.get_value():
            self.selected_ref = self.best_ref.get_value()
            self.update_ref_SG_UCC(self.selected_ref)
            
    def update_ref_SG_UCC(self, ref_file):
        print("updating REF ucc and sg")
        ref_dir = os.path.dirname(ref_file)
        ascii_file = os.path.join(ref_dir, "XDS_ASCII.HKL")
        print(ascii_file)
        self.REF = os.path.join(self.dir_entry.get_value(), "REF.hkl")
        with open(self.REF, 'w') as file:
            # Optionally, write some initial data
            file.write("")

        with open(ascii_file, 'r') as file:
            file_contents = file.readlines()
        print("done reading")
        SG_pattern = "!SPACE_GROUP_NUMBER="
        UCC_pattern = "!UNIT_CELL_CONSTANTS=" 
        #updates
        for line in file_contents:
            try:
                if re.search(SG_pattern, line):
                    if self.SG.get_value():
                        line = f"{SG_pattern}\t{self.SG.get_value()}\n"
                        # print("SG found")
                    else:
                        print("SG empty")
                        self.REF
                        return
                if re.search(UCC_pattern, line):
                    #UNIT_CELL_CONSTANTS=   101.490    60.601    63.094  90.000 116.196  90.000
                    if self.UCC_a.get_value() and self.UCC_b.get_value() and self.UCC_c.get_value():
                        
                        # Remove the label part before splitting
                        line = line.split('=')[1].strip()
                        
                        # Use regex to find all numbers
                        numbers = re.findall(r'\d+\.\d+', line)
                        
                        numbers[0] = self.UCC_a.get_value()
                        numbers[1] = self.UCC_b.get_value()
                        numbers[2] = self.UCC_c.get_value()
                        ucc = '\t'.join(numbers)
                        line= f"{UCC_pattern}\t{ucc}\n"
                    else:
                        print("ucc empty")
                        messagebox.showerror("Error", f"UCC and/or SG are empty in tab 'Data'")
                        return
            except TypeError:
                pass
                    
            with open(self.REF, 'a') as file:
                # Optionally, write some initial data
                file.write(line)  
        print("done writing REF")
        if os.path.isfile(self.REF):
            self.check_mark_label = ctk.CTkLabel(self.Reindexing_content_frame, image=self.check_mark_photo, text="")
            self.check_mark_label.grid(row=2, column=4, padx=10, pady=10)
                
    def find_ref_button_function(self, value):
        if value == 'Auto':
            self.find_best_ref(self.dir_entry.get())
        elif value == 'Auto-guided':
            self.thread_show_top_refs()
        elif value == 'Manual':
            self.browse_ref()
            
    def find_best_ref(self, directory):
        self.REF = None
        files = self.find_files(directory, '**/CORRECT.LP')
        self.nb_of_refs=len(files)
        best_reference = self.find_reference(files, 1)
        mode = ctk.get_appearance_mode()
        textcolor = "black" if mode == "Light" else "white"

        if best_reference:
            best_ref, _ = best_reference
            print("looking for the best ref automatically!")
            print(f"best ref is {best_ref}")
            self.best_ref.configure(state="normal")
            self.best_ref.delete(0, "end")
            self.best_ref.set_value(best_ref)
            self.best_ref.configure(state="readonly", text_color="black", fg_color="#E0E0E0")
            self.ref_option_table.configure(text="")
            self.correctlp_header.configure(text="")
            self.update_canvas_size(self.Reindexing_canvas,self.Reindexing_content_frame)
            self.reindexing_h_scrollbar.update_scrollbar_visibility()
            self.reindexing_v_scrollbar.update_scrollbar_visibility()
            print("\n\nshould have been ran\n\n")
            self.previous_selection_find_ref = self.find_ref_button.get()
            try: 
                self.refs_options.destroy()
                self.refs_options = None
            except AttributeError:
                # print("nothing to destroy")
                pass

        else:
            self.find_ref_button.set(self.previous_selection_find_ref)
            print("No results found")

    def find_reference(self, files, ranking):
        all_results = []
        for file in files:
            all_results.extend(self.grep_total(file))
        sorted_results = sorted(
            all_results,
            key=lambda x: float(x[1].split()[8]) if len(x[1].split()) > 8 else float('-inf')
        )
       
        if sorted_results:
            key = int(f"-{ranking}")
            best_ref, last_line = sorted_results[key]
            return best_ref, last_line 
        else:
            print("No results found")
            
    def extract_correctlp_table(self, correctlp_path):
        """Search for lines containing 'total' in the given file."""
        table = []
        look_for_total = False
        checkpoint="RESOLUTION     NUMBER OF REFLECTIONS    COMPLETENESS R-FACTOR  R-FACTOR COMPARED I/SIGMA   R-meas  CC(1/2)  Anomal  SigAno   Nano"
        checkpoint_normalized = re.sub(r'\s+', ' ', checkpoint).strip()
        try:
            with open(correctlp_path, 'r') as file:
                for line in file:
                    line_normalized = re.sub(r'\s+', ' ', line).strip()
                    if checkpoint_normalized in line_normalized:
                        # print("found the table")
                        look_for_total = True
                        next(file)
                        next(file)
                    if look_for_total and line.strip()[0].isdigit():
                        table.append(line.strip())
                    if 'total' in line and look_for_total:
                        table.append(line.strip())
                        break
        except IOError:
            pass  # Handle file read errors
        return table

    def thread_show_top_refs(self):
        threading.Thread(target=self.show_top_refs, args=(self.dir_entry.get(),)).start()

    def show_top_refs(self, directory):
        self.REF = None
        self.refs_hall_of_fame = []
        mode = ctk.get_appearance_mode()
        textcolor = "black" if mode == "Light" else "white"

        if self.dir_entry.get() == self.dir_placeholder:
            print("no input directory yet!")
            self.find_ref_button.set(self.previous_selection_find_ref)
            return
        # header="RESOLUTION     NUMBER OF REFLECTIONS    COMPLETENESS R-FACTOR  R-FACTOR COMPARED I/SIGMA   R-meas  CC(1/2)  Anomal  SigAno   Nano\n
        #           LIMIT     OBSERVED  UNIQUE  POSSIBLE     OF DATA   observed  expected                                      Corr                "
        header="RES\tRO\tRU\tRP\tCOM\tRFO\tRFE\tRFC\tISIG\tRMEAS\tCC12\tANO\tSIGA\tNANO"
        def show_table(selected_value):
            correctlp = selected_value.split(" - ")[1]
            self.best_ref.configure(state="normal")
            self.best_ref.delete(0, "end")
            self.best_ref.set_value(correctlp)
            self.best_ref.configure(state="readonly", text_color="black", fg_color="#E0E0E0")
            self.previous_selection_find_ref = self.find_ref_button.get()
            table = refs_tables.get(correctlp)

            table_as_text = self.format_table_for_output(table)
            self.correctlp_header.configure(text=header)
            self.ref_option_table.configure(text=table_as_text)
            self.correctlp_header.update_idletasks()
            self.update_canvas_size(self.Reindexing_canvas,self.Reindexing_content_frame)
            self.reindexing_h_scrollbar.update_scrollbar_visibility()
            self.reindexing_v_scrollbar.update_scrollbar_visibility()
            
        def on_arrow_key(event):
            # Get the current value
            current_value = self.refs_options.get() 
            # Find the index of the current value
            if current_value in self.refs_hall_of_fame:
                current_index = self.refs_hall_of_fame.index(current_value)
            else:
                current_index = -1  # Not found or no item selected
            if event.keysym == "Up":
                # Move up
                new_index = (current_index - 1) % len(self.refs_hall_of_fame)
                show_table(self.refs_hall_of_fame[new_index])
            elif event.keysym == "Down":
                # Move down
                new_index = (current_index + 1) % len(self.refs_hall_of_fame)
                show_table(self.refs_hall_of_fame[new_index])
            else:
                return
            self.refs_options.set(self.refs_hall_of_fame[new_index])  # Update the displayed value
            
        if self.refs_options is None:
            self.refs_options = ctk.CTkComboBox(self.Reindexing_content_frame, command=lambda value: show_table(value), width=300)
            self.refs_options.grid(row=2, column=2, columnspan=2, padx=10, pady=10)
            # Bind the arrow keys
            self.refs_options.bind("<Up>", on_arrow_key)
            self.refs_options.bind("<Down>", on_arrow_key)
            
        
            
        files = self.find_files(directory, '**/CORRECT.LP')
        nb_of_refs=len(files)
        self.best_ref.configure(state="normal")
        self.best_ref.delete(0, "end")
        self.best_ref.configure(state="readonly")
        top_refs = [None]*nb_of_refs
        top_table = [None]*nb_of_refs
        refs_tables = {}
        value_0 = None
        self.progress_window = tk.Toplevel(self)
        self.progress_window.title("Searching for CORRECT.LPs")
        self.progress_label = tk.Label(self.progress_window, text="In progress ..", padx=10, pady=10, anchor="w")
        self.progress_label.pack(pady=10, anchor="w")
        width = 800
        height = 100
        # Center the window
        self.center_window(self.progress_window, width, height)


        # Create and add a Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self.progress_window, mode="determinate")
        self.progress_bar.pack(pady=10, padx=10, fill='x')

        
        for i in range(nb_of_refs):
            top_refs[i] = self.find_reference(files, i+1)[0]
            top_table[i] = (self.extract_correctlp_table(top_refs[i]))
            refs_tables[top_refs[i]] = top_table[i]
            value = f"{i} - {top_refs[i]}"
            if value_0 is None: value_0 = value
            self.combobox_append_refs(value)
            
            if value in self.refs_hall_of_fame:
                print(f"value alraedy appended: {value}")
            self.refs_hall_of_fame.append(value)
            self.progress_label.config(text=value)
            self.progress_bar.set(i / nb_of_refs)  # Set the progress (normalized to 0-1)
            self.progress_window.update_idletasks()
        self.progress_window.destroy()
        
        self.refs_options.set(value_0)
        show_table(value_0)

    def center_window(self, window, width, height):
        # Get screen width and height
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Calculate position x, y
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
        # Set the window size and position
        window.geometry(f"{width}x{height}+{x}+{y}")

    def combobox_append_refs(self, new_values):
        # Get current values (returns a tuple)
        current_values = self.refs_options.cget("values")
        # Check if current_values is empty (when initialized with no values)
        if not current_values:
            current_values = []
        # Append new values
        updated_values = current_values+[new_values]
        # Update ComboBox with new values
        self.refs_options.configure(values=updated_values)
    
    def format_table_for_output(self, table):
        def normalize_data(raw_data):
            normalized = []
            for line in raw_data:
                # Replace multiple spaces with a single space
                line = ' '.join(line.split())
                normalized.append(line)
            return normalized
        def convert_to_table(normalized_data):
            table = [line.split(' ') for line in normalized_data]
            return table

        table = normalize_data(table)
        table = convert_to_table(table)
        # Ensure table is a list of lists
        if not all(isinstance(row, list) for row in table):
            raise ValueError("Table should be a list of lists.")

        # Determine maximum column width for formatting
        column_widths = [max(len(str(item)) for item in column) for column in zip(*table)]

        formatted_rows = []
        for row in table:
            # Format each item in the row to align with the column width
            formatted_row = '\t'.join(f"{str(item).ljust(width)}" for item, width in zip(row, column_widths))
            formatted_rows.append(formatted_row)

        return '\n'.join(formatted_rows)

    def browse_ref(self):
        ref = ""
        ref = filedialog.askopenfilename()
        print(f"ref is {ref}")
        mode = ctk.get_appearance_mode()
        textcolor = "black" if mode == "Light" else "white"

        if ref != "":
            self.best_ref.configure(state="normal")
            self.best_ref.delete(0, "end")
            self.best_ref.set_value(ref)
            self.best_ref.configure(state="readonly", text_color="black", fg_color="#E0E0E0")
            self.ref_option_table.configure(text="")
            self.correctlp_header.configure(text="")
            self.previous_selection_find_ref = self.find_ref_button.get()
            try: 
                self.refs_options.destroy()
                self.refs_options = None
            except AttributeError:
                print("no table to destroy")
                pass
            self.update_canvas_size(self.Reindexing_canvas,self.Reindexing_content_frame)
            self.reindexing_h_scrollbar.update_scrollbar_visibility()
            self.reindexing_v_scrollbar.update_scrollbar_visibility()
            self.REF = ref
            self.set_ref_button.configure(state="disabled",fg_color="gray")
        else:
            self.find_ref_button.set(self.previous_selection_find_ref)


# plots UCC                
    def download_plots(self):
        dpi = simpledialog.askinteger("DPI", "Enter DPI (e.g., 100, 200):", minvalue=1, maxvalue=1000)
        if dpi:
            for detail in self.fig_details_entries:
                fig, title, filename_pattern = detail
                fig_name = str(filename_pattern) + "_" + str(title) + "_DPI" + str(dpi) + ".png"
                fig_path = os.path.join(self.dir_entry.get(), fig_name)
                fig.savefig(fig_path, dpi=dpi)
            messagebox.showinfo("Downloaded", f"Figures of UCC collected from datasets with pattern {filename_pattern} were saved in {self.dir_entry.get()}")

    def fitting_plots(self, value):
        if value == 'Fit H':
            self.fitplots_byHeight()
            # self.update_scrollbars()
        elif value == 'Fit W':
            self.fitplots_byWidth()
            # self.update_scrollbars()

    def fitplots_byHeight(self):
        plot_h = round(self.canvas_plots.winfo_height()-80, 0)
        for plot in self.plots_canvases:
            plot.config(width=plot_h, height=plot_h)
        self.indexing_plots_frame.update_idletasks()
        self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
        self.fit_by="height"
        self.indexing_h_scrollbar.update_scrollbar_visibility()
        self.indexing_v_scrollbar.update_scrollbar_visibility()

    def fitplots_byWidth(self):
        plot_w = round((self.canvas_plots.winfo_width()-80)/3, 0)
        for plot in self.plots_canvases:
            plot.config(width=plot_w, height=plot_w)
        self.indexing_plots_frame.update_idletasks()
        self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
        self.fit_by="width"
        self.indexing_h_scrollbar.update_scrollbar_visibility()
        self.indexing_v_scrollbar.update_scrollbar_visibility()

    def get_default_bg_color(self):
        mode = ctk.get_appearance_mode()
        if mode == "Light":
            return "gray86"
        else:
            return "gray17"        

    def update_dpi_value(self, event):
        self.dpi = int(self.dpi_box.get())
        for widget in self.indexing_plots_frame.winfo_children():
            widget.destroy()
        self.plots_canvases = []
        # print(self.plots_info_entries.items())
        for filename_pattern, plots_starting_row in self.plots_info_entries.items():
            self.plotted = False
            self.plot_all_ucc(self.dir_entry.get(),filename_pattern, self.dpi, plots_starting_row)

    def open_figure_in_new_window(self, fig):
        # Create a new top-level window
        new_window = tk.Toplevel(self)
        new_window.title("Figure")

        # Create a higher resolution figure for the new window
        fig_new = Figure(figsize=(6, 4), dpi=150)
        ax_new = fig_new.add_subplot(111)

        # Extract data from the original figure's histogram patches
        for ax in fig.axes:
            for patch in ax.patches:
                # Extract the data from the patch
                x = patch.get_x()  # x-coordinate of the rectangle's left side
                width = patch.get_width()  # width of the rectangle
                height = patch.get_height()  # height of the rectangle

                # Plot this data in the new figure
                ax_new.bar(x, height, width=width, alpha=0.7, color="blue", edgecolor="#483D8B")

        # Copy other plot attributes
        if fig.axes:
            source_ax = fig.axes[0]
            ax_new.set_title(source_ax.get_title())
            ax_new.set_xlabel(source_ax.get_xlabel())
            ax_new.set_ylabel(source_ax.get_ylabel())            

        # Create a canvas for the new window
        canvas = FigureCanvasTkAgg(fig_new, master=new_window)
        canvas.draw()

        # Create and add the navigation toolbar
        toolbar = NavigationToolbar2Tk(canvas, new_window)
        toolbar.pack(side=tk.TOP, fill=tk.X)  # Pack toolbar first
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Update the window to ensure the toolbar is rendered and get its height
        new_window.update_idletasks()
        toolbar.update_idletasks()

        def adjust_canvas_size():
            new_window.update_idletasks()  # Ensure all updates are processed
            toolbar_height = toolbar.winfo_height()
            available_height = new_window.winfo_height() - toolbar_height

            # Adjust the figure size to fit the window
            fig_new_width = new_window.winfo_width()
            fig_new_height = available_height
            
            # Update figure size
            fig_new.set_size_inches(fig_new_width / fig_new.dpi, fig_new_height / fig_new.dpi, forward=True)
            
            # Redraw the canvas to reflect the updated figure size
            canvas.draw()

        # Schedule the function to run after the window is displayed
        new_window.after(100, adjust_canvas_size)
        # Store the canvas and figure in the new window
        new_window.canvas = canvas
        new_window.fig = fig_new

    def plot_all_ucc(self, directory, filename_pattern, dpi, plots_starting_row):
        if not filename_pattern in self.plots_info_entries or not self.plotted:
            plots_info = ctk.CTkLabel(self.indexing_plots_frame, text=f"Unit cell distribution among datasets with files: {filename_pattern}")
            plots_info.grid(row=plots_starting_row, column=0, columnspan=4, padx=(10,10), pady=(0,0), sticky="w")
            row=plots_starting_row+1
            (_,a,a_mean,a_std,b,b_mean,b_std,c,c_mean,c_std,target_files_counter)=self.collect_sg_cell(directory, filename_pattern)
            self.plot_ucc_histograms(a, "a", row, 0, dpi,filename_pattern)
            self.plot_ucc_histograms(b, "b", row, 1, dpi,filename_pattern)
            self.plot_ucc_histograms(c, "c", row, 2, dpi,filename_pattern)
            # Update the scroll region of the canvas to include the content
            self.indexing_plots_frame.update_idletasks()
            self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
            self.plotted = True
            self.download_plots.configure(state="normal", fg_color=self.default_button_fg_color)
            if not filename_pattern in self.plots_info_entries:
                self.plots_info_entries[filename_pattern] = plots_starting_row
                self.plots_starting_row += 2
            self.indexing_h_scrollbar.update_scrollbar_visibility()
            self.indexing_v_scrollbar.update_scrollbar_visibility()
        else:
            print("already plotted")
            
    def plot_ucc_histograms(self, ucc, name, row, col, dpi, filename_pattern):
        # Remove existing frame in the specified grid cell
        for widget in self.indexing_plots_frame.grid_slaves(row=row, column=col):
            widget.destroy()
        
        # Create a frame for the plot within the tab
        self.frame = ctk.CTkFrame(self.indexing_plots_frame, width=100)
        self.frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Configure grid row and column weights
        self.indexing_plots_frame.grid_rowconfigure(row, weight=1)
        self.indexing_plots_frame.grid_columnconfigure(col, weight=1)
        self.frame.grid_rowconfigure(row, weight=1)
        self.frame.grid_columnconfigure(col, weight=1)

        try:
            # Create a Matplotlib figure and plot
            fig, ax = plt.subplots(figsize=(3, 3), dpi=dpi)  # Adjust size as needed
            self.fig_entries.append(fig)
            sns.histplot(ucc, bins=100, kde=False, ax=ax)
            ax.axvline(np.min(ucc), color='r', linestyle='dashed', linewidth=1, label=f'Min: {np.min(ucc)}')
            ax.axvline(np.max(ucc), color='g', linestyle='dashed', linewidth=1, label=f'Max: {np.max(ucc)}')
            ax.axvline(np.mean(ucc), color='b', linestyle='dashed', linewidth=1, label=f'Mean: {np.mean(ucc):.2f}')
            ax.axvline(np.mean(ucc) + np.std(ucc), color='y', linestyle='dashed', linewidth=1, label=f'Std Dev: {np.std(ucc):.2f}')
            ax.axvline(np.mean(ucc) - np.std(ucc), color='y', linestyle='dashed', linewidth=1)
            ax.legend(fontsize=7, loc='upper right')
            ax.set_title(f'Unit cell constant {name}', fontsize=9)
            ax.set_xlabel('Value', fontsize=9)
            ax.set_ylabel('Frequency', fontsize=9)
            title=f'Unit cell constant {name}'
            self.fig_details_entries.append([fig,title,filename_pattern])
        finally:
            plt.close('all')  # Ensure all figures are closed
        
        # Create a canvas to display the plot and add it to the frame
        canvas = FigureCanvasTkAgg(fig, master=self.frame)
        canvas_height = self.canvas_plots.winfo_height()-20
        canvas_width = (self.canvas_plots.winfo_width()-60)/3
        canvas.draw()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.bind("<Button-1>", lambda event, f=fig: self.open_figure_in_new_window(f))

        if self.fit_by == "height":
            canvas_widget.config(width=canvas_height, height=canvas_height)
        else:
            canvas_widget.config(width=canvas_width, height=canvas_width)
        canvas_widget.grid(row=0, column=0, sticky="nsew")  # Ensure proper grid placement
        self.plots_canvases.append(canvas_widget)
        gc.collect()

    def plot_SG_pie_chart(self, directory, target_filename):
        if os.path.isfile(directory+f"/cell_param_{target_filename}.log"):
            data = np.genfromtxt(directory+f"/cell_param_{target_filename}.log")
            data = data[:,1]
        else:
            data = self.collect_sg_cell(directory, target_filename)
            data = data[0]
        
        # Count occurrences
        unique_values, counts = np.unique(data, return_counts=True)

        # Plot pie chart
        plt.figure(figsize=(4,4))
        plt.pie(counts, labels=unique_values, autopct='%1.1f%%', startangle=140)
        plt.title('Space Group(s)')
        plt.show()

    def on_resize(self, event):
        # If a resize event is already scheduled, cancel it
        if self._resize_after:
            self.after_cancel(self._resize_after)

        # Schedule a resize event to be called after a short delay
        self._resize_after = self.after(500, self.resize_action)

    def resize_action(self):
        current_size = self.winfo_width(), self.winfo_height()
        if current_size != self.previous_size:
            # Get the new size of the window
            width, height = self.winfo_width(), self.winfo_height()
            # Update the dimensions of the CTkTabview
            self.tabview.configure(width=width, height=height)
            # resize plots canvas
            plot_height = self.canvas_plots.winfo_height()-20
            plot_width = (self.canvas_plots.winfo_width()-60)/3

            if self.plotted:
                if self.fit_by == "height":
                    for plot in self.plots_canvases:
                        plot.config(width=plot_height, height=plot_height)
                if self.fit_by == "width":
                    for plot in self.plots_canvases:
                        plot.config(width=plot_width, height=plot_width)

            self.indexing_plots_frame.update_idletasks()
            self.Reindexing_canvas.update_idletasks()
            self.canvas_plots.config(scrollregion=self.canvas_plots.bbox("all"))
            self.previous_size = current_size
            self.indexing_h_scrollbar.update_scrollbar_visibility()
            self.indexing_v_scrollbar.update_scrollbar_visibility()
            # self.update_scrollbars()
            gc.collect()
        else:
            pass


    # def on_press(self, event):
    #     # Store the start position of the zoom box
    #     self.press = (event.x, event.y)

    # def on_drag(self, event):
    #     if hasattr(self, 'press'):
    #         x1, y1 = self.press
    #         x2, y2 = event.x, event.y

    #         # Access the figure from the appropriate canvas
    #         if hasattr(self, 'canvas') and hasattr(self.canvas, 'figure'):
    #             fig = self.canvas.figure
    #             ax = fig.axes[0]  # Use the new figure's axes

    #             # Adjust the view limits based on the mouse drag
    #             ax.set_xlim([x1, x2])
    #             ax.set_ylim([y1, y2])
    #             fig.canvas.draw()
                        

# browse and combobox es
               
    def on_combo_box_select(self, event):
        selected_option = self.combo_box.get()
        temp_entry = ctk.CTkEntry(self)
        default_fg_color = temp_entry.cget("fg_color")
        temp_entry.destroy()
        # Enable or disable the entry based on the selected option
        if selected_option == "other":
            self.filename_entry.configure(state="normal", fg_color=default_fg_color)  # Enable entry
            self.filename_entry.delete(0, "end")
            self.filename_entry.focus()
            # self.filename_var.trace_add("write", self.other_pattern)
            # self.filename_pattern = self.filename_entry.get_value()
            # self.other_pattern
        else:
            self.filename_entry.delete(0, "end")  # Clear any existing text
            self.filename_entry.insert(0, self.filename_placeholder)
            self.filename_entry.configure(state="disabled", text_color="grey", fg_color=self.disabled_entry_fgcolor)  # Disable entry
            self.filename_pattern = selected_option

    def other_pattern(self, pattern):
        self.filename_pattern = pattern
        # self.filename_entry.set_value(self.filename_entry.get())
        # print("other pattern set: ", self.filename_pattern)

    def mcr_browse_path(self):
        mcr_script = filedialog.askopenfilename()
        if mcr_script:
            print("Selected file:", mcr_script)
            self.mcr_path.delete(0, 'end')
            # self.mcr_path.configure(text_color="black")
            self.mcr_path.set_value(mcr_script)

    def browse_file(self):
        directory_path = filedialog.askdirectory()
        if directory_path:
            self.dir_entry.delete(0, 'end')
            self.dir_entry.set_value(directory_path)
 
 
 # sidebar               
    def open_documentation_url(self):
        webbrowser.open("https://sites.google.com/site/codgas1/overview?authuser=0")

    def copy_citation(self):
        citation = "Zander, U., Cianci, M., Foos, N., Silva, C.S., Mazzei, L., Zubieta, C., de Maria, A. & Nanao, M.H. (2016). Acta Cryst. D72, doi:10.1107/S2059798316012079"
        try:
            self.clipboard_append(citation)  # Append text to the clipboard
            self.update()  # Update the clipboard
            messagebox.showinfo("Success", f"Citation copied to clipboard! \n{citation}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy citation: {e}")
            print(f"Failed to copy citation: {e}")

    def view_parameters(self):
        best_ref = self.selected_ref if self.selected_ref else self.best_ref.get()
        best_ref_ASCII = os.path.join(os.path.dirname(best_ref), "XDS_ASCII.HKL")
        if not os.path.isfile(best_ref_ASCII):
            best_ref_ASCII = "does not exist"
        messagebox.showinfo("Parameters", "User entered values                                                                             \n\n"f"Directory:   {self.dir_entry.get()}\n"
                            f"Spacegroup:   {self.SG.get()}\n"
                            f"Unit cell a:  {self.UCC_a.get_value()}\n"
                            f"Unit cell b:  {self.UCC_b.get()}\n"
                            f"Unit cell c:  {self.UCC_c.get()}\n"
                            f"File name pattern:  {self.filename_pattern}\n"
                            f"REF dataset: {best_ref_ASCII}")


   
    def SG_INFO(self):
        webbrowser.open("http://img.chem.ucl.ac.uk/sgp/large/sgp.htm")


# tools        
    def find_and_log_unit_cell_constants(self, directory, filename_pattern):
        # print("function was called!!!!!!!!!!!")
        target_filename = filename_pattern
        search_pattern1 = "SPACE_GROUP_NUMBER="
        search_pattern2 = "UNIT_CELL_CONSTANTS"
        log_file_path = os.path.join(directory, f"cell_param_{target_filename}.log")
        target_files_counter = 0
        # Open the log file for appending
        with open(log_file_path, "w") as log_file:
            # Walk through the directory structure up to a depth of 2
            for root, dirs, files in os.walk(directory):
                # Calculate the current depth
                depth = root[len(directory):].count(os.sep)
                if depth > 2:
                    # If the depth is more than 2, skip further directories
                    dirs[:] = []
                    continue

                # Check each file in the current directory
                for file in files:
                    if file == target_filename:
                        # Construct the full path of the file
                        file_path = os.path.join(root, file)
                        
                        try:
                            # Open the file and search for the pattern
                            with open(file_path, 'r') as f:
                                for line in f:
                                    if search_pattern1 in line:
                                        # Write the matching line to the log file
                                        log_file.write(f"{file_path}:\t{line.split()[1]}")
                                        # break  # Stop after the first match
                                    if search_pattern2 in line:
                                        # Write the matching line to the log file
                                        ucc_list = line.split()[1:7]
                                        UCC = '\t'.join(map(str, ucc_list))
                                        log_file.write(f"  {UCC} \n")
                                        break  # Stop after the first match
                            target_files_counter += 1
                        except Exception as e:
                            print(f"An error occurred while processing {file_path}: {e}")
        return target_files_counter

    def collect_sg_cell(self, directory, target_filename):
        target_files_counter=self.find_and_log_unit_cell_constants(directory, target_filename)            
        data = np.genfromtxt(directory+f"/cell_param_{target_filename}.log")
        sg = data[:,1] ; sg = sg.astype(int)
        a = data[:,2] ; a = a.astype(float) ; a_mean = round(np.mean(a), 2) ; a_std = round(np.std(a), 2)
        b = data[:,3] ; b = b.astype(float) ; b_mean = round(np.mean(b), 2) ; b_std = round(np.std(b), 2)
        c = data[:,4] ; c = c.astype(float) ; c_mean = round(np.mean(c), 2) ; c_std = round(np.std(c), 2)
        return(sg,a,a_mean,a_std,b,b_mean,b_std,c,c_mean,c_std,target_files_counter)
    
    def find_files(self, directory, pattern):
        """Find files matching the given pattern in the specified directory."""
        search_pattern = os.path.join(directory, pattern)
        found_files = glob.glob(search_pattern, recursive=True)
        return list(set(found_files))
    
    def grep_total(self, file_path):
        """Search for lines containing 'total' in the given file."""
        results = []
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if 'total' in line:
                        results.append((file_path, line.strip()))
        except IOError:
            pass  # Handle file read errors
        return results

    def memory_usage(self):
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        return mem_info.rss  # Return memory usage in bytes
 



        
if __name__ == "__main__":
    app = App()
    app.mainloop()
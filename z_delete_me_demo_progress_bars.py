#!/usr/bin/env python3
"""
Demo script showing what progress bars look like in the enhanced workflow control centre display
"""

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.box import HEAVY
from shared.progress_display_utils import ProgressDisplayUtils

def demo_progress_bars():
    """Show what enhanced progress display looks like"""
    console = Console()
    
    print("Enhanced Workflow Control Centre - Progress Display Demo")
    print("=" * 60)
    print()
    
    # Create demo enhanced table showing progress bars
    table = Table(title="WORKFLOW PROGRESSION BY PROJECT", box=HEAVY, show_header=True)
    
    # Add columns
    table.add_column("Project", width=20, style="cyan", no_wrap=True)
    table.add_column("(C)apture", width=13, justify="center", no_wrap=False)
    table.add_column("(D)ecode", width=13, justify="center", no_wrap=False) 
    table.add_column("Co(m)press", width=13, justify="center", no_wrap=False)
    table.add_column("(E)xport", width=13, justify="center", no_wrap=False)
    table.add_column("(A)lign", width=13, justify="center", no_wrap=False)
    table.add_column("(F)inal", width=13, justify="center", no_wrap=False)
    
    # Demo row 1: Various progress states
    def create_progress_cell(percentage, fps=None, eta_text=None):
        """Create a demo multi-line progress cell"""
        if percentage <= 0:
            return Text("Processing...", style="yellow")
        
        # Create progress bar
        progress_bar = ProgressDisplayUtils.create_progress_bar(percentage, width=11)
        
        # Create multi-line cell
        multiline_text = Text()
        multiline_text.append(Text(progress_bar, style="green"))
        multiline_text.append("\n")
        
        # Second line: percentage and fps
        fps_text = f" {fps:.1f}fps" if fps else ""
        percentage_line = f"{percentage:.1f}%{fps_text}"
        multiline_text.append(Text(percentage_line, style="cyan"))
        multiline_text.append("\n")
        
        # Third line: ETA
        eta_display = eta_text if eta_text else "ETA: --:--"
        multiline_text.append(Text(eta_display, style="yellow" if eta_text else "dim"))
        
        return multiline_text
    
    # Row 1: Metallica1 - Running export job
    table.add_row(
        "1. Metallica1",
        Text("Complete", style="green"),
        Text("Complete", style="green"),
        Text("Ready", style="white"),
        create_progress_cell(45.3, fps=28.5, eta_text="ETA 8m"),  # Export running
        Text("Complete", style="green"),
        Text("Ready", style="white")
    )
    
    # Row 2: Wedding_Video - Running decode
    table.add_row(
        "2. Wedding_Video",  
        Text("Complete", style="green"),
        create_progress_cell(72.1, fps=15.2, eta_text="ETA 3m"),  # Decode running
        Text("Missing", style="dim"),
        Text("Missing", style="dim"),
        Text("N/A", style="dim"),
        Text("Missing", style="dim")
    )
    
    # Row 3: Kids_Birthday - Just started (0% progress)
    table.add_row(
        "3. Kids_Birthday",
        Text("Complete", style="green"),
        create_progress_cell(0),  # Just started decode
        Text("Missing", style="dim"),
        Text("Missing", style="dim"),
        Text("Missing", style="dim"),
        Text("Missing", style="dim")
    )
    
    # Row 4: Theater_Performance - Nearly complete export
    table.add_row(
        "4. Theater_Performance",
        Text("Complete", style="green"),
        Text("Complete", style="green"), 
        Text("Missing", style="dim"),
        create_progress_cell(94.7, fps=42.1, eta_text="ETA 1m"),  # Export almost done
        Text("Ready", style="white"),
        Text("Missing", style="dim")
    )
    
    # Row 5: Family_Reunion - No running jobs
    table.add_row(
        "5. Family_Reunion",
        Text("Complete", style="green"),
        Text("Ready", style="white"),
        Text("Missing", style="dim"), 
        Text("Missing", style="dim"),
        Text("Ready", style="white"),
        Text("Missing", style="dim")
    )
    
    console.print(table)
    
    print("\nDemonstration Features:")
    print("✅ Multi-line progress cells with:")
    print("   • Visual progress bars using ███░░░ characters")
    print("   • Real-time percentage and FPS display")
    print("   • ETA calculations for running jobs")
    print("   • 'Processing...' indicator for 0% progress jobs")
    print("✅ Color coding:")
    print("   • Green progress bars for active jobs")
    print("   • Cyan text for percentage and FPS")
    print("   • Yellow text for ETA information")
    print("   • Standard colors for other statuses")
    print("✅ Compact display fitting workflow matrix columns")
    
    print(f"\nProgress Bar Examples:")
    for percent in [0, 25, 45.3, 72.1, 94.7, 100]:
        bar = ProgressDisplayUtils.create_progress_bar(percent, width=11)
        print(f"  {percent:5.1f}%: [{bar}]")

if __name__ == "__main__":
    demo_progress_bars()

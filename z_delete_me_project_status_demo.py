#!/usr/bin/env python3
"""
Demo of colored project status display
"""

try:
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
    console = Console()
except ImportError:
    print("Rich library not available - install with: pip install rich")
    exit(1)

def create_colored_status(status_text, status_type):
    """Create colored status text based on type"""
    colors = {
        'complete': 'green',
        'failed': 'red', 
        'video_only': 'orange3',
        'ready': 'white',
        'running': 'blue',
        'queued': 'bright_black'
    }
    
    color = colors.get(status_type, 'white')
    return Text(status_text, style=color)

def demo_project_status():
    """Demo the colored project status table"""
    
    console.print("\n[bold]PROJECT WORKFLOW STATUS[/bold]")
    console.print("=" * 80)
    
    # Create the table
    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Project", style="cyan", width=20)
    table.add_column("Capture", justify="center", width=11)
    table.add_column("Decode", justify="center", width=10)
    table.add_column("Compress", justify="center", width=9)
    table.add_column("Export", justify="center", width=10)
    table.add_column("Align", justify="center", width=11)
    table.add_column("Final", justify="center", width=11)
    
    # Sample projects with different statuses
    projects = [
        {
            'name': 'Movie_Night_1985',
            'capture': ('Complete', 'complete'),
            'decode': ('Complete', 'complete'),
            'compress': ('Ready', 'ready'),
            'export': ('Complete', 'complete'),
            'align': ('Ready', 'ready'),
            'final': ('Ready', 'ready')
        },
        {
            'name': 'Wedding_Video_1987',
            'capture': ('Complete', 'complete'),
            'decode': ('Complete', 'complete'),
            'compress': ('Complete', 'complete'),
            'export': ('Complete', 'complete'),
            'align': ('Complete', 'complete'),
            'final': ('Complete', 'complete')
        },
        {
            'name': 'Kids_Birthday_1990',
            'capture': ('Complete', 'complete'),
            'decode': ('Failed', 'failed'),
            'compress': ('Queued', 'queued'),
            'export': ('Queued', 'queued'),
            'align': ('Queued', 'queued'),
            'final': ('Queued', 'queued')
        },
        {
            'name': 'Theater_Performance',
            'capture': ('Complete', 'complete'),
            'decode': ('Running', 'running'),
            'compress': ('Queued', 'queued'),
            'export': ('Queued', 'queued'),
            'align': ('Queued', 'queued'),
            'final': ('Queued', 'queued')
        },
        {
            'name': 'Family_Reunion_92',
            'capture': ('Video Only', 'video_only'),
            'decode': ('Ready', 'ready'),
            'compress': ('Queued', 'queued'),
            'export': ('Queued', 'queued'),
            'align': ('Queued', 'queued'),
            'final': ('Queued', 'queued')
        },
        {
            'name': 'Vacation_Highlights',
            'capture': ('Complete', 'complete'),
            'decode': ('Ready', 'ready'),
            'compress': ('Queued', 'queued'),
            'export': ('Queued', 'queued'),
            'align': ('Ready', 'ready'),
            'final': ('Queued', 'queued')
        }
    ]
    
    # Add rows to table
    for project in projects:
        table.add_row(
            project['name'],
            create_colored_status(project['capture'][0], project['capture'][1]),
            create_colored_status(project['decode'][0], project['decode'][1]),
            create_colored_status(project['compress'][0], project['compress'][1]),
            create_colored_status(project['export'][0], project['export'][1]),
            create_colored_status(project['align'][0], project['align'][1]),
            create_colored_status(project['final'][0], project['final'][1])
        )
    
    console.print(table)
    
    # Status legend
    console.print("\n[bold]Status Legend:[/bold]")
    legend_table = Table(show_header=False, box=None, padding=(0, 2))
    legend_table.add_column("Status", style="white")
    legend_table.add_column("Description", style="bright_black")
    
    legend_items = [
        (create_colored_status("Complete", "complete"), "Step finished successfully"),
        (create_colored_status("Failed", "failed"), "Error occurred, needs attention"),
        (create_colored_status("Video Only", "video_only"), "No audio present, only video will be processed"),
        (create_colored_status("Ready", "ready"), "Prerequisites met, can start"),
        (create_colored_status("Running", "running"), "Currently being processed - See Job Status Screen"),
        (create_colored_status("Queued", "queued"), "Waiting in job queue")
    ]
    
    for status, description in legend_items:
        legend_table.add_row(status, description)
    
    console.print(legend_table)
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold] 6 projects • 2 ready for decode • 1 decode running • 1 decode failed • 1 complete workflow")

if __name__ == "__main__":
    demo_project_status()

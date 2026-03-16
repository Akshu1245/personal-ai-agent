"""
============================================================
AKSHAY AI CORE — Data Analysis Plugin
============================================================
Data processing, analysis, and visualization tools.
============================================================
"""

from typing import Any, Dict, List, Optional

from plugins.base import BuiltinPlugin, PluginMetadata, PluginConfig
from core.utils.logger import get_logger

logger = get_logger("plugin.data_analysis")


class DataAnalysisPlugin(BuiltinPlugin):
    """
    Data analysis plugin.
    
    Commands:
    - load_data: Load data from file
    - describe: Get data statistics
    - query: Query data with SQL-like syntax
    - transform: Transform data
    - visualize: Create visualizations
    - export: Export processed data
    """
    
    metadata = PluginMetadata(
        name="data_analysis",
        version="1.0.0",
        description="Data processing, analysis, and visualization",
        author="AKSHAY AI CORE",
        tags=["data", "analysis", "visualization", "statistics"],
    )
    
    config = PluginConfig(
        enabled=True,
        sandboxed=True,
        max_execution_time=300,
        permissions=["file:read", "file:write", "tool:data_analysis"],
        settings={
            "max_rows": 1000000,
            "output_dir": "./data/analysis",
        },
    )
    
    def __init__(self):
        super().__init__()
        self._datasets: Dict[str, Any] = {}
    
    async def on_load(self) -> None:
        """Initialize data analysis plugin."""
        self.register_command("load_data", self._cmd_load_data, "Load data from file")
        self.register_command("describe", self._cmd_describe, "Get data statistics")
        self.register_command("query", self._cmd_query, "Query data")
        self.register_command("transform", self._cmd_transform, "Transform data")
        self.register_command("visualize", self._cmd_visualize, "Create visualizations")
        self.register_command("export", self._cmd_export, "Export data")
        
        logger.info("Data analysis plugin loaded")
    
    async def execute(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a data analysis command."""
        return await self.dispatch_command(command, params)
    
    async def _cmd_load_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load data from a file."""
        import pandas as pd
        from pathlib import Path
        
        file_path = params.get("path")
        name = params.get("name")
        
        if not file_path:
            return {"status": "error", "error": "File path required"}
        
        path = Path(file_path)
        if not path.exists():
            return {"status": "error", "error": "File not found"}
        
        name = name or path.stem
        
        try:
            # Detect file type and load
            suffix = path.suffix.lower()
            
            if suffix == ".csv":
                df = pd.read_csv(path)
            elif suffix in (".xlsx", ".xls"):
                df = pd.read_excel(path)
            elif suffix == ".json":
                df = pd.read_json(path)
            elif suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                return {"status": "error", "error": f"Unsupported file type: {suffix}"}
            
            # Limit rows
            max_rows = self.config.settings.get("max_rows", 1000000)
            if len(df) > max_rows:
                df = df.head(max_rows)
                logger.warning(f"Dataset truncated to {max_rows} rows")
            
            self._datasets[name] = df
            
            return {
                "status": "success",
                "name": name,
                "rows": len(df),
                "columns": list(df.columns),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_describe(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get descriptive statistics of data."""
        name = params.get("name")
        
        if not name or name not in self._datasets:
            return {"status": "error", "error": "Dataset not found"}
        
        df = self._datasets[name]
        
        # Generate statistics
        stats = df.describe(include='all').to_dict()
        
        return {
            "status": "success",
            "name": name,
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing": df.isnull().sum().to_dict(),
            "statistics": stats,
        }
    
    async def _cmd_query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Query data using pandas query syntax."""
        name = params.get("name")
        query = params.get("query")
        
        if not name or name not in self._datasets:
            return {"status": "error", "error": "Dataset not found"}
        
        if not query:
            return {"status": "error", "error": "Query required"}
        
        df = self._datasets[name]
        
        try:
            result = df.query(query)
            
            return {
                "status": "success",
                "rows": len(result),
                "data": result.head(100).to_dict(orient='records'),
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_transform(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data."""
        name = params.get("name")
        operation = params.get("operation")
        output_name = params.get("output", name)
        
        if not name or name not in self._datasets:
            return {"status": "error", "error": "Dataset not found"}
        
        df = self._datasets[name].copy()
        
        try:
            if operation == "drop_na":
                df = df.dropna()
            
            elif operation == "fill_na":
                value = params.get("value", 0)
                df = df.fillna(value)
            
            elif operation == "sort":
                by = params.get("by")
                ascending = params.get("ascending", True)
                df = df.sort_values(by=by, ascending=ascending)
            
            elif operation == "filter":
                column = params.get("column")
                condition = params.get("condition")
                value = params.get("value")
                
                if condition == "eq":
                    df = df[df[column] == value]
                elif condition == "gt":
                    df = df[df[column] > value]
                elif condition == "lt":
                    df = df[df[column] < value]
                elif condition == "contains":
                    df = df[df[column].str.contains(value, na=False)]
            
            elif operation == "groupby":
                by = params.get("by")
                agg = params.get("agg", "count")
                df = df.groupby(by).agg(agg).reset_index()
            
            else:
                return {"status": "error", "error": f"Unknown operation: {operation}"}
            
            self._datasets[output_name] = df
            
            return {
                "status": "success",
                "name": output_name,
                "rows": len(df),
                "columns": list(df.columns),
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_visualize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create visualizations."""
        name = params.get("name")
        chart_type = params.get("type", "line")
        x = params.get("x")
        y = params.get("y")
        output = params.get("output")
        
        if not name or name not in self._datasets:
            return {"status": "error", "error": "Dataset not found"}
        
        df = self._datasets[name]
        
        try:
            import matplotlib.pyplot as plt
            from pathlib import Path
            
            fig, ax = plt.subplots(figsize=(10, 6))
            
            if chart_type == "line":
                df.plot(x=x, y=y, kind='line', ax=ax)
            elif chart_type == "bar":
                df.plot(x=x, y=y, kind='bar', ax=ax)
            elif chart_type == "scatter":
                df.plot(x=x, y=y, kind='scatter', ax=ax)
            elif chart_type == "hist":
                df[y or x].plot(kind='hist', ax=ax)
            elif chart_type == "pie":
                df.plot(y=y, kind='pie', ax=ax)
            else:
                return {"status": "error", "error": f"Unknown chart type: {chart_type}"}
            
            # Save
            if not output:
                from datetime import datetime
                output = f"./data/analysis/chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
            
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(output)
            plt.close()
            
            return {
                "status": "success",
                "chart_type": chart_type,
                "output": output,
            }
            
        except ImportError:
            return {"status": "error", "error": "matplotlib not installed"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    async def _cmd_export(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Export data to file."""
        name = params.get("name")
        output = params.get("output")
        format_type = params.get("format", "csv")
        
        if not name or name not in self._datasets:
            return {"status": "error", "error": "Dataset not found"}
        
        if not output:
            return {"status": "error", "error": "Output path required"}
        
        df = self._datasets[name]
        
        try:
            from pathlib import Path
            
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if format_type == "csv":
                df.to_csv(path, index=False)
            elif format_type == "json":
                df.to_json(path, orient='records')
            elif format_type == "excel":
                df.to_excel(path, index=False)
            elif format_type == "parquet":
                df.to_parquet(path, index=False)
            else:
                return {"status": "error", "error": f"Unknown format: {format_type}"}
            
            return {
                "status": "success",
                "output": str(path),
                "format": format_type,
                "rows": len(df),
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

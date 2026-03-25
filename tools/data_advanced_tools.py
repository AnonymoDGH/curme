"""
═══════════════════════════════════════════════════════════════════════════════
📊 DATA PROCESSING AVANZADO - Enterprise Edition
═══════════════════════════════════════════════════════════════════════════════

Suite completa de herramientas para procesamiento y análisis de datos:
- Profiling exhaustivo de datasets
- Pipelines ETL configurables
- Validación de calidad de datos
- Conversión de formatos (Parquet, CSV, JSON)
- Resampling de series temporales
- Anonimización GDPR-compliant

Dependencias:
pip install pandas numpy pyarrow fastparquet ydata-profiling great_expectations
pip install faker hashlib cryptography openpyxl sqlalchemy
"""

import os
import re
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

from .base import BaseTool, ToolParameter

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS CONDICIONALES
# ═══════════════════════════════════════════════════════════════════════════════

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False

try:
    from ydata_profiling import ProfileReport
    HAS_PROFILING = True
except ImportError:
    HAS_PROFILING = False

try:
    from faker import Faker
    HAS_FAKER = True
except ImportError:
    HAS_FAKER = False

try:
    import sqlalchemy
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DATA PROFILER TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class DataProfilerTool(BaseTool):
    """Genera perfil completo de datasets"""
    
    name = "data_profiler"
    description = """Genera análisis exhaustivo de datasets.
    
Análisis incluido:
  ‣ Estadísticas descriptivas completas
  ‣ Distribuciones de variables
  ‣ Análisis de valores faltantes
  ‣ Matriz de correlación
  ‣ Detección de outliers
  ‣ Análisis de cardinalidad
  ‣ Detección de duplicados
  ‣ Inferencia de tipos de datos
  ‣ Análisis de texto (para strings)
  ‣ Recomendaciones de limpieza
  
Outputs:
  - Reporte HTML interactivo (opcional)
  - JSON con métricas
  - Resumen en texto"""
    
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "data_path": ToolParameter(
                name="data_path",
                type="string",
                description="Ruta del dataset (CSV, Excel, JSON, Parquet)",
                required=True
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta para guardar reporte HTML",
                required=False
            ),
            "generate_html": ToolParameter(
                name="generate_html",
                type="boolean",
                description="Generar reporte HTML interactivo (requiere ydata-profiling)",
                required=False
            ),
            "sample_size": ToolParameter(
                name="sample_size",
                type="integer",
                description="Número de filas a muestrear (None = todas)",
                required=False
            ),
            "correlation_threshold": ToolParameter(
                name="correlation_threshold",
                type="number",
                description="Umbral para correlaciones altas (default: 0.8)",
                required=False
            )
        }
    
    def execute(
        self,
        data_path: str = None,
        output_path: str = None,
        generate_html: bool = False,
        sample_size: int = None,
        correlation_threshold: float = 0.8,
        **kwargs
    ) -> str:
        if not HAS_PANDAS:
            return "[x] Instala: pip install pandas numpy"
        
        data_path = data_path or kwargs.get('data_path')
        output_path = output_path or kwargs.get('output_path')
        generate_html = kwargs.get('generate_html', generate_html)
        sample_size = sample_size or kwargs.get('sample_size')
        correlation_threshold = correlation_threshold or kwargs.get('correlation_threshold', 0.8)
        
        if not data_path:
            return "[x] Se requiere 'data_path'"
        
        try:
            # Cargar datos
            print(f"📊 Cargando dataset: {data_path}")
            df = self._load_dataset(data_path)
            
            # Muestrear si es necesario
            if sample_size and len(df) > sample_size:
                print(f"📉 Muestreando {sample_size} filas de {len(df)}")
                df = df.sample(n=sample_size, random_state=42)
            
            original_rows = len(df)
            
            # Generar perfil
            print("🔍 Analizando dataset...")
            profile = self._generate_profile(df, correlation_threshold)
            
            # Generar reporte HTML si se solicitó
            html_path = None
            if generate_html:
                if HAS_PROFILING:
                    print("📄 Generando reporte HTML...")
                    html_path = self._generate_html_report(df, output_path)
                else:
                    print("⚠️  ydata-profiling no disponible, saltando reporte HTML")
            
            # Formatear resultado
            result = self._format_profile_report(profile, Path(data_path).name, html_path)
            
            # Guardar perfil en JSON
            if output_path:
                json_path = Path(output_path).parent / f"{Path(output_path).stem}_profile.json"
                with open(json_path, 'w') as f:
                    json.dump(profile, f, indent=2, default=str)
                result += f"\n\n💾 **Perfil JSON guardado:** {json_path.absolute()}"
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error analizando datos: {e}\n\n{traceback.format_exc()}"
    
    def _load_dataset(self, path: str) -> pd.DataFrame:
        """Carga dataset desde múltiples formatos"""
        
        path_obj = Path(path)
        suffix = path_obj.suffix.lower()
        
        if suffix == '.csv':
            return pd.read_csv(path)
        elif suffix in ['.xlsx', '.xls']:
            return pd.read_excel(path)
        elif suffix == '.json':
            return pd.read_json(path)
        elif suffix == '.parquet':
            if HAS_PYARROW:
                return pd.read_parquet(path)
            else:
                raise ImportError("Instala: pip install pyarrow")
        else:
            # Intentar CSV por defecto
            return pd.read_csv(path)
    
    def _generate_profile(self, df: pd.DataFrame, corr_threshold: float) -> Dict:
        """Genera perfil completo del dataset"""
        
        profile = {
            'overview': self._get_overview(df),
            'variables': self._analyze_variables(df),
            'missing': self._analyze_missing(df),
            'duplicates': self._analyze_duplicates(df),
            'correlations': self._analyze_correlations(df, corr_threshold),
            'outliers': self._detect_outliers(df),
            'recommendations': []
        }
        
        # Generar recomendaciones
        profile['recommendations'] = self._generate_recommendations(profile)
        
        return profile
    
    def _get_overview(self, df: pd.DataFrame) -> Dict:
        """Información general del dataset"""
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        datetime_cols = df.select_dtypes(include=['datetime64']).columns
        
        return {
            'rows': len(df),
            'columns': len(df.columns),
            'numeric_columns': len(numeric_cols),
            'categorical_columns': len(categorical_cols),
            'datetime_columns': len(datetime_cols),
            'memory_usage_mb': df.memory_usage(deep=True).sum() / 1024**2,
            'total_missing': df.isnull().sum().sum(),
            'total_duplicates': df.duplicated().sum()
        }
    
    def _analyze_variables(self, df: pd.DataFrame) -> Dict:
        """Analiza cada variable del dataset"""
        
        variables = {}
        
        for col in df.columns:
            var_info = {
                'dtype': str(df[col].dtype),
                'count': df[col].count(),
                'missing': df[col].isnull().sum(),
                'missing_pct': (df[col].isnull().sum() / len(df)) * 100,
                'unique': df[col].nunique(),
                'unique_pct': (df[col].nunique() / len(df)) * 100
            }
            
            # Estadísticas para numéricos
            if pd.api.types.is_numeric_dtype(df[col]):
                var_info.update({
                    'mean': df[col].mean(),
                    'std': df[col].std(),
                    'min': df[col].min(),
                    'q25': df[col].quantile(0.25),
                    'median': df[col].median(),
                    'q75': df[col].quantile(0.75),
                    'max': df[col].max(),
                    'skew': df[col].skew(),
                    'kurtosis': df[col].kurtosis()
                })
            
            # Estadísticas para categóricos
            elif pd.api.types.is_object_dtype(df[col]):
                value_counts = df[col].value_counts()
                var_info.update({
                    'top_values': value_counts.head(10).to_dict(),
                    'mode': df[col].mode()[0] if len(df[col].mode()) > 0 else None,
                    'avg_length': df[col].astype(str).str.len().mean()
                })
            
            variables[col] = var_info
        
        return variables
    
    def _analyze_missing(self, df: pd.DataFrame) -> Dict:
        """Análisis detallado de valores faltantes"""
        
        missing_counts = df.isnull().sum()
        missing_pct = (missing_counts / len(df)) * 100
        
        # Columnas con missing values
        cols_with_missing = missing_counts[missing_counts > 0].sort_values(ascending=False)
        
        # Patrones de missing
        missing_patterns = {}
        if len(cols_with_missing) > 0:
            # Combinaciones de columnas con missing
            missing_matrix = df[cols_with_missing.index].isnull()
            pattern_counts = missing_matrix.value_counts().head(10)
            
            for pattern, count in pattern_counts.items():
                pattern_str = ', '.join([
                    col for col, is_missing in zip(cols_with_missing.index, pattern) 
                    if is_missing
                ])
                if pattern_str:
                    missing_patterns[pattern_str] = count
        
        return {
            'total_missing': missing_counts.sum(),
            'columns_with_missing': len(cols_with_missing),
            'missing_by_column': cols_with_missing.to_dict(),
            'missing_pct_by_column': missing_pct[missing_pct > 0].to_dict(),
            'patterns': missing_patterns
        }
    
    def _analyze_duplicates(self, df: pd.DataFrame) -> Dict:
        """Análisis de duplicados"""
        
        total_duplicates = df.duplicated().sum()
        
        if total_duplicates == 0:
            return {
                'total_duplicates': 0,
                'duplicate_pct': 0,
                'duplicate_rows': []
            }
        
        # Encontrar duplicados
        duplicates = df[df.duplicated(keep=False)]
        
        # Grupos de duplicados
        duplicate_groups = []
        for _, group in duplicates.groupby(list(df.columns)):
            if len(group) > 1:
                duplicate_groups.append({
                    'count': len(group),
                    'sample': group.head(1).to_dict('records')[0]
                })
        
        return {
            'total_duplicates': total_duplicates,
            'duplicate_pct': (total_duplicates / len(df)) * 100,
            'duplicate_groups': len(duplicate_groups),
            'sample_groups': duplicate_groups[:5]  # Solo primeros 5
        }
    
    def _analyze_correlations(self, df: pd.DataFrame, threshold: float) -> Dict:
        """Análisis de correlaciones"""
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_cols) < 2:
            return {
                'high_correlations': [],
                'correlation_matrix': {}
            }
        
        # Calcular matriz de correlación
        corr_matrix = df[numeric_cols].corr()
        
        # Encontrar correlaciones altas
        high_corr = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                col1 = corr_matrix.columns[i]
                col2 = corr_matrix.columns[j]
                corr_value = corr_matrix.iloc[i, j]
                
                if abs(corr_value) >= threshold:
                    high_corr.append({
                        'var1': col1,
                        'var2': col2,
                        'correlation': corr_value
                    })
        
        # Ordenar por correlación absoluta
        high_corr.sort(key=lambda x: abs(x['correlation']), reverse=True)
        
        return {
            'high_correlations': high_corr,
            'correlation_matrix': corr_matrix.to_dict()
        }
    
    def _detect_outliers(self, df: pd.DataFrame) -> Dict:
        """Detecta outliers en columnas numéricas"""
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        outliers = {}
        
        for col in numeric_cols:
            # Método IQR
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_count = outlier_mask.sum()
            
            if outlier_count > 0:
                outliers[col] = {
                    'count': outlier_count,
                    'percentage': (outlier_count / len(df)) * 100,
                    'lower_bound': lower_bound,
                    'upper_bound': upper_bound,
                    'min_outlier': df[outlier_mask][col].min(),
                    'max_outlier': df[outlier_mask][col].max()
                }
        
        return outliers
    
    def _generate_recommendations(self, profile: Dict) -> List[str]:
        """Genera recomendaciones basadas en el perfil"""
        
        recommendations = []
        
        # Missing values
        if profile['missing']['total_missing'] > 0:
            missing_pct = (profile['missing']['total_missing'] / 
                          (profile['overview']['rows'] * profile['overview']['columns'])) * 100
            
            if missing_pct > 20:
                recommendations.append(
                    f"⚠️  Alto porcentaje de valores faltantes ({missing_pct:.1f}%). "
                    "Considerar imputación o eliminación de columnas."
                )
        
        # Duplicates
        if profile['duplicates']['total_duplicates'] > 0:
            dup_pct = profile['duplicates']['duplicate_pct']
            if dup_pct > 5:
                recommendations.append(
                    f"⚠️  {dup_pct:.1f}% de filas duplicadas. Revisar y eliminar duplicados."
                )
        
        # Correlaciones altas
        high_corr = profile['correlations']['high_correlations']
        if len(high_corr) > 0:
            recommendations.append(
                f"📊 {len(high_corr)} pares de variables altamente correlacionadas. "
                "Considerar eliminación de features redundantes."
            )
        
        # Outliers
        outlier_cols = len(profile['outliers'])
        if outlier_cols > 0:
            recommendations.append(
                f"📈 Outliers detectados en {outlier_cols} columnas. "
                "Revisar y decidir tratamiento (eliminar, transformar, cap)."
            )
        
        # Cardinalidad alta
        for col, info in profile['variables'].items():
            if info['unique_pct'] > 95 and info['dtype'] == 'object':
                recommendations.append(
                    f"🔑 '{col}' tiene cardinalidad muy alta ({info['unique_pct']:.1f}%). "
                    "Posible ID o feature no útil."
                )
        
        # Columnas constantes
        for col, info in profile['variables'].items():
            if info['unique'] == 1:
                recommendations.append(
                    f"⚠️  '{col}' es constante (único valor). Considerar eliminación."
                )
        
        if not recommendations:
            recommendations.append("✅ Dataset en buenas condiciones. No se detectaron problemas mayores.")
        
        return recommendations
    
    def _generate_html_report(self, df: pd.DataFrame, output_path: str = None) -> str:
        """Genera reporte HTML con ydata-profiling"""
        
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"profile_report_{timestamp}.html"
        
        profile = ProfileReport(
            df,
            title="Dataset Profile Report",
            explorative=True,
            dark_mode=False
        )
        
        profile.to_file(output_path)
        
        return str(Path(output_path).absolute())
    
    def _format_profile_report(self, profile: Dict, dataset_name: str, html_path: str = None) -> str:
        """Formatea reporte del perfil"""
        
        overview = profile['overview']
        missing = profile['missing']
        duplicates = profile['duplicates']
        
        result = f"""✅ **Perfil del Dataset: {dataset_name}**

📊 **Overview:**
  - Filas: {overview['rows']:,}
  - Columnas: {overview['columns']}
    • Numéricas: {overview['numeric_columns']}
    • Categóricas: {overview['categorical_columns']}
    • Datetime: {overview['datetime_columns']}
  - Memoria: {overview['memory_usage_mb']:.2f} MB
  - Missing values: {overview['total_missing']:,} ({(overview['total_missing']/(overview['rows']*overview['columns'])*100):.1f}%)
  - Duplicados: {overview['total_duplicates']:,} ({(overview['total_duplicates']/overview['rows']*100):.1f}%)

"""
        
        # Columnas con missing
        if missing['columns_with_missing'] > 0:
            result += "❌ **Valores Faltantes (Top 10):**\n"
            sorted_missing = sorted(
                missing['missing_by_column'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            for col, count in sorted_missing:
                pct = (count / overview['rows']) * 100
                bar = '█' * int(pct / 5)
                result += f"  {col:30} {bar:20} {count:>6,} ({pct:>5.1f}%)\n"
            result += "\n"
        
        # Correlaciones altas
        high_corr = profile['correlations']['high_correlations']
        if len(high_corr) > 0:
            result += f"🔗 **Correlaciones Altas (>{0.8}):**\n"
            for corr in high_corr[:10]:
                result += f"  {corr['var1']} ↔ {corr['var2']}: {corr['correlation']:.3f}\n"
            result += "\n"
        
        # Outliers
        outliers = profile['outliers']
        if len(outliers) > 0:
            result += f"📈 **Outliers Detectados ({len(outliers)} columnas):**\n"
            for col, info in list(outliers.items())[:10]:
                result += f"  {col:30} {info['count']:>6,} ({info['percentage']:>5.1f}%)\n"
            result += "\n"
        
        # Variables con problemas
        problem_vars = []
        for col, info in profile['variables'].items():
            if info['unique'] == 1:
                problem_vars.append(f"  ⚠️  {col}: Constante")
            elif info['unique_pct'] > 95 and info['dtype'] == 'object':
                problem_vars.append(f"  🔑 {col}: Cardinalidad muy alta ({info['unique_pct']:.1f}%)")
            elif info['missing_pct'] > 50:
                problem_vars.append(f"  ❌ {col}: >50% missing ({info['missing_pct']:.1f}%)")
        
        if problem_vars:
            result += "⚠️  **Variables Problemáticas:**\n"
            result += "\n".join(problem_vars[:10])
            result += "\n\n"
        
        # Recomendaciones
        result += "💡 **Recomendaciones:**\n"
        for rec in profile['recommendations']:
            result += f"  {rec}\n"
        
        if html_path:
            result += f"\n\n📄 **Reporte HTML:** {html_path}"
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ETL PIPELINE TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class ETLPipelineTool(BaseTool):
    """Ejecuta pipelines ETL configurables"""
    
    name = "etl_pipeline"
    description = """Ejecuta pipelines ETL configurables.
    
Operaciones soportadas:
  ‣ Extract: CSV, JSON, Excel, Parquet, SQL
  ‣ Transform: Filter, Map, Aggregate, Join, Sort
  ‣ Load: CSV, JSON, Parquet, SQL, Excel
  
Configuración mediante JSON:
```json
{
  "extract": {
    "source": "data.csv",
    "type": "csv"
  },
  "transform": [
    {"operation": "filter", "condition": "age > 18"},
    {"operation": "select", "columns": ["name", "age"]},
    {"operation": "sort", "by": "age", "ascending": false}
  ],
  "load": {
    "destination": "output.parquet",
    "type": "parquet"
  }
}
```"""
    
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "config_path": ToolParameter(
                name="config_path",
                type="string",
                description="Ruta del archivo de configuración JSON",
                required=False
            ),
            "config_json": ToolParameter(
                name="config_json",
                type="string",
                description="Configuración ETL en formato JSON string",
                required=False
            ),
            "source": ToolParameter(
                name="source",
                type="string",
                description="Ruta del archivo fuente (alternativa simple)",
                required=False
            ),
            "destination": ToolParameter(
                name="destination",
                type="string",
                description="Ruta del archivo destino (alternativa simple)",
                required=False
            ),
            "operations": ToolParameter(
                name="operations",
                type="string",
                description="Operaciones separadas por comas: filter:age>18,select:name|age",
                required=False
            )
        }
    
    def execute(
        self,
        config_path: str = None,
        config_json: str = None,
        source: str = None,
        destination: str = None,
        operations: str = None,
        **kwargs
    ) -> str:
        if not HAS_PANDAS:
            return "[x] Instala: pip install pandas numpy"
        
        config_path = config_path or kwargs.get('config_path')
        config_json = config_json or kwargs.get('config_json')
        source = source or kwargs.get('source')
        destination = destination or kwargs.get('destination')
        operations = operations or kwargs.get('operations')
        
        try:
            # Cargar configuración
            if config_path:
                with open(config_path) as f:
                    config = json.load(f)
            elif config_json:
                config = json.loads(config_json)
            else:
                # Configuración simple
                if not source:
                    return "[x] Se requiere 'source' o 'config_path' o 'config_json'"
                
                config = {
                    'extract': {'source': source, 'type': self._infer_type(source)},
                    'transform': self._parse_operations(operations) if operations else [],
                    'load': {'destination': destination or 'output.csv', 'type': self._infer_type(destination or 'output.csv')}
                }
            
            # Ejecutar pipeline
            print("🔄 Iniciando pipeline ETL...")
            
            # EXTRACT
            print(f"📥 Extrayendo datos de: {config['extract']['source']}")
            df = self._extract(config['extract'])
            initial_rows = len(df)
            
            # TRANSFORM
            if 'transform' in config and config['transform']:
                print(f"🔧 Aplicando {len(config['transform'])} transformaciones...")
                df, transform_log = self._transform(df, config['transform'])
            else:
                transform_log = []
            
            # LOAD
            print(f"💾 Cargando datos a: {config['load']['destination']}")
            self._load(df, config['load'])
            
            # Resumen
            result = f"""✅ **Pipeline ETL Completado**

📥 **Extract:**
  - Fuente: {config['extract']['source']}
  - Tipo: {config['extract']['type']}
  - Filas: {initial_rows:,}

🔧 **Transform:**
  - Operaciones: {len(transform_log)}
"""
            
            if transform_log:
                for log in transform_log:
                    result += f"  ✓ {log}\n"
            
            result += f"""
💾 **Load:**
  - Destino: {config['load']['destination']}
  - Tipo: {config['load']['type']}
  - Filas finales: {len(df):,}
  - Columnas: {len(df.columns)}

📊 **Resultado:**
  - Filas procesadas: {initial_rows:,} → {len(df):,}
  - Reducción: {((initial_rows - len(df))/initial_rows*100):.1f}%
"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error en pipeline ETL: {e}\n\n{traceback.format_exc()}"
    
    def _infer_type(self, path: str) -> str:
        """Infiere tipo de archivo"""
        suffix = Path(path).suffix.lower()
        
        type_map = {
            '.csv': 'csv',
            '.json': 'json',
            '.xlsx': 'excel',
            '.xls': 'excel',
            '.parquet': 'parquet',
            '.sql': 'sql'
        }
        
        return type_map.get(suffix, 'csv')
    
    def _parse_operations(self, operations_str: str) -> List[Dict]:
        """Parsea string de operaciones a lista de dicts"""
        
        operations = []
        
        for op_str in operations_str.split(','):
            op_str = op_str.strip()
            
            if ':' in op_str:
                op_type, op_params = op_str.split(':', 1)
                
                if op_type == 'filter':
                    operations.append({
                        'operation': 'filter',
                        'condition': op_params
                    })
                elif op_type == 'select':
                    operations.append({
                        'operation': 'select',
                        'columns': op_params.split('|')
                    })
                elif op_type == 'sort':
                    operations.append({
                        'operation': 'sort',
                        'by': op_params
                    })
        
        return operations
    
    def _extract(self, config: Dict) -> pd.DataFrame:
        """Extrae datos de fuente"""
        
        source = config['source']
        source_type = config['type']
        
        if source_type == 'csv':
            return pd.read_csv(source)
        
        elif source_type == 'json':
            return pd.read_json(source)
        
        elif source_type == 'excel':
            return pd.read_excel(source)
        
        elif source_type == 'parquet':
            if HAS_PYARROW:
                return pd.read_parquet(source)
            else:
                raise ImportError("Instala: pip install pyarrow")
        
        elif source_type == 'sql':
            if not HAS_SQLALCHEMY:
                raise ImportError("Instala: pip install sqlalchemy")
            
            engine = sqlalchemy.create_engine(config.get('connection_string'))
            query = config.get('query', f"SELECT * FROM {config.get('table')}")
            return pd.read_sql(query, engine)
        
        else:
            raise ValueError(f"Tipo de fuente no soportado: {source_type}")
    
    def _transform(self, df: pd.DataFrame, operations: List[Dict]) -> Tuple[pd.DataFrame, List[str]]:
        """Aplica transformaciones"""
        
        log = []
        
        for op in operations:
            operation = op['operation']
            
            if operation == 'filter':
                # Filtrar filas
                condition = op['condition']
                initial_rows = len(df)
                df = df.query(condition)
                log.append(f"Filter: '{condition}' ({initial_rows:,} → {len(df):,} filas)")
            
            elif operation == 'select':
                # Seleccionar columnas
                columns = op['columns']
                df = df[columns]
                log.append(f"Select: {len(columns)} columnas")
            
            elif operation == 'drop':
                # Eliminar columnas
                columns = op['columns']
                df = df.drop(columns=columns)
                log.append(f"Drop: {len(columns)} columnas eliminadas")
            
            elif operation == 'rename':
                # Renombrar columnas
                mapping = op['mapping']
                df = df.rename(columns=mapping)
                log.append(f"Rename: {len(mapping)} columnas")
            
            elif operation == 'sort':
                # Ordenar
                by = op['by']
                ascending = op.get('ascending', True)
                df = df.sort_values(by=by, ascending=ascending)
                log.append(f"Sort: por '{by}' ({'ASC' if ascending else 'DESC'})")
            
            elif operation == 'fillna':
                # Rellenar nulos
                value = op.get('value')
                method = op.get('method')
                
                if value is not None:
                    df = df.fillna(value)
                    log.append(f"FillNA: valor={value}")
                elif method:
                    df = df.fillna(method=method)
                    log.append(f"FillNA: method={method}")
            
            elif operation == 'dropna':
                # Eliminar nulos
                initial_rows = len(df)
                df = df.dropna()
                log.append(f"DropNA: {initial_rows:,} → {len(df):,} filas")
            
            elif operation == 'deduplicate':
                # Eliminar duplicados
                initial_rows = len(df)
                subset = op.get('subset')
                df = df.drop_duplicates(subset=subset)
                log.append(f"Deduplicate: {initial_rows:,} → {len(df):,} filas")
            
            elif operation == 'aggregate':
                # Agregar
                groupby = op['groupby']
                aggregations = op['aggregations']
                df = df.groupby(groupby).agg(aggregations).reset_index()
                log.append(f"Aggregate: group by {groupby}")
            
            elif operation == 'join':
                # Join con otro dataset
                right_path = op['right']
                right_df = pd.read_csv(right_path)
                
                on = op.get('on')
                how = op.get('how', 'inner')
                
                df = df.merge(right_df, on=on, how=how)
                log.append(f"Join: {how} join con {Path(right_path).name}")
            
            else:
                log.append(f"⚠️  Operación no reconocida: {operation}")
        
        return df, log
    
    def _load(self, df: pd.DataFrame, config: Dict):
        """Carga datos a destino"""
        
        destination = config['destination']
        dest_type = config['type']
        
        # Crear directorio si no existe
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        
        if dest_type == 'csv':
            df.to_csv(destination, index=False)
        
        elif dest_type == 'json':
            df.to_json(destination, orient='records', indent=2)
        
        elif dest_type == 'excel':
            df.to_excel(destination, index=False)
        
        elif dest_type == 'parquet':
            if HAS_PYARROW:
                df.to_parquet(destination, index=False)
            else:
                raise ImportError("Instala: pip install pyarrow")
        
        elif dest_type == 'sql':
            if not HAS_SQLALCHEMY:
                raise ImportError("Instala: pip install sqlalchemy")
            
            engine = sqlalchemy.create_engine(config.get('connection_string'))
            table_name = config.get('table')
            if_exists = config.get('if_exists', 'replace')
            
            df.to_sql(table_name, engine, if_exists=if_exists, index=False)
        
        else:
            raise ValueError(f"Tipo de destino no soportado: {dest_type}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DATA QUALITY CHECK TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class DataQualityCheckTool(BaseTool):
    """Valida calidad de datos con reglas"""
    
    name = "data_quality_check"
    description = """Valida calidad de datos con reglas personalizadas.
    
Tipos de validaciones:
  ‣ not_null: Columna no debe tener nulos
  ‣ unique: Valores deben ser únicos
  ‣ range: Valores en rango [min, max]
  ‣ pattern: Valores que matchean regex
  ‣ type: Tipo de dato esperado
  ‣ values: Valores permitidos (whitelist)
  ‣ custom: Query pandas custom
  
Configuración JSON:
```json
{
  "rules": [
    {"column": "email", "check": "pattern", "pattern": "^[\\w\\.]+@[\\w]+\\.[a-z]{2,}$"},
    {"column": "age", "check": "range", "min": 0, "max": 120},
    {"column": "status", "check": "values", "allowed": ["active", "inactive"]}
  ]
}
```"""
    
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "data_path": ToolParameter(
                name="data_path",
                type="string",
                description="Ruta del dataset a validar",
                required=True
            ),
            "rules_path": ToolParameter(
                name="rules_path",
                type="string",
                description="Ruta del archivo de reglas JSON",
                required=False
            ),
            "rules_json": ToolParameter(
                name="rules_json",
                type="string",
                description="Reglas en formato JSON string",
                required=False
            ),
            "output_report": ToolParameter(
                name="output_report",
                type="string",
                description="Ruta para guardar reporte de calidad",
                required=False
            ),
            "fail_fast": ToolParameter(
                name="fail_fast",
                type="boolean",
                description="Detener en primera validación fallida",
                required=False
            )
        }
    
    def execute(
        self,
        data_path: str = None,
        rules_path: str = None,
        rules_json: str = None,
        output_report: str = None,
        fail_fast: bool = False,
        **kwargs
    ) -> str:
        if not HAS_PANDAS:
            return "[x] Instala: pip install pandas"
        
        data_path = data_path or kwargs.get('data_path')
        rules_path = rules_path or kwargs.get('rules_path')
        rules_json = rules_json or kwargs.get('rules_json')
        output_report = output_report or kwargs.get('output_report')
        fail_fast = kwargs.get('fail_fast', fail_fast)
        
        if not data_path:
            return "[x] Se requiere 'data_path'"
        
        try:
            # Cargar datos
            print(f"📊 Cargando dataset: {data_path}")
            df = pd.read_csv(data_path)
            
            # Cargar reglas
            if rules_path:
                with open(rules_path) as f:
                    rules_config = json.load(f)
            elif rules_json:
                rules_config = json.loads(rules_json)
            else:
                # Reglas por defecto: validaciones básicas
                rules_config = self._generate_default_rules(df)
            
            rules = rules_config.get('rules', [])
            
            print(f"✅ Ejecutando {len(rules)} validaciones...")
            
            # Ejecutar validaciones
            results = []
            passed = 0
            failed = 0
            
            for rule in rules:
                result = self._validate_rule(df, rule)
                results.append(result)
                
                if result['passed']:
                    passed += 1
                else:
                    failed += 1
                    
                    if fail_fast:
                        break
            
            # Generar reporte
            report = self._generate_quality_report(df, results, passed, failed)
            
            # Guardar reporte
            if output_report:
                report_path = Path(output_report)
                with open(report_path, 'w') as f:
                    # Preprocesar results para JSON
                    results_serializable = []
                    for r in results:
                        r_copy = {}
                        for k, v in r.items():
                            if isinstance(v, (bool, np.bool_)):
                                r_copy[k] = bool(v)
                            elif isinstance(v, (int, np.integer)):
                                r_copy[k] = int(v)
                            elif isinstance(v, (float, np.floating)):
                                r_copy[k] = float(v)
                            else:
                                r_copy[k] = v
                        results_serializable.append(r_copy)
                    
                    json.dump({
                        'dataset': str(data_path),
                        'timestamp': datetime.now().isoformat(),
                        'total_rules': len(rules),
                        'passed': int(passed) if not isinstance(passed, bool) else passed,
                        'failed': int(failed) if not isinstance(failed, bool) else failed,
                        'results': results_serializable
                    }, f, indent=2)
                
                report += f"\n\n💾 **Reporte guardado:** {report_path.absolute()}"
            
            return report
            
        except Exception as e:
            import traceback
            return f"[x] Error validando calidad: {e}\n\n{traceback.format_exc()}"
    
    def _generate_default_rules(self, df: pd.DataFrame) -> Dict:
        """Genera reglas por defecto basadas en el dataset"""
        
        rules = []
        
        # Not null para todas las columnas
        for col in df.columns:
            if df[col].isnull().sum() == 0:  # Si actualmente no tiene nulos
                rules.append({
                    'column': col,
                    'check': 'not_null'
                })
        
        # Unique para columnas con todos valores únicos
        for col in df.columns:
            if df[col].nunique() == len(df):
                rules.append({
                    'column': col,
                    'check': 'unique'
                })
        
        return {'rules': rules}
    
    def _validate_rule(self, df: pd.DataFrame, rule: Dict) -> Dict:
        """Valida una regla"""
        
        column = rule['column']
        check = rule['check']
        
        result = {
            'column': column,
            'check': check,
            'passed': False,
            'message': '',
            'failed_count': 0,
            'failed_pct': 0
        }
        
        if column not in df.columns:
            result['message'] = f"Columna '{column}' no existe"
            return result
        
        try:
            if check == 'not_null':
                # No debe tener nulos
                null_count = df[column].isnull().sum()
                result['failed_count'] = null_count
                result['failed_pct'] = (null_count / len(df)) * 100
                result['passed'] = null_count == 0
                result['message'] = f"{'✓' if result['passed'] else '✗'} {null_count:,} valores nulos"
            
            elif check == 'unique':
                # Valores deben ser únicos
                duplicate_count = df[column].duplicated().sum()
                result['failed_count'] = duplicate_count
                result['failed_pct'] = (duplicate_count / len(df)) * 100
                result['passed'] = duplicate_count == 0
                result['message'] = f"{'✓' if result['passed'] else '✗'} {duplicate_count:,} duplicados"
            
            elif check == 'range':
                # Valores en rango
                min_val = rule.get('min')
                max_val = rule.get('max')
                
                mask = (df[column] >= min_val) & (df[column] <= max_val)
                failed_count = (~mask).sum()
                
                result['failed_count'] = failed_count
                result['failed_pct'] = (failed_count / len(df)) * 100
                result['passed'] = failed_count == 0
                result['message'] = f"{'✓' if result['passed'] else '✗'} Rango [{min_val}, {max_val}]: {failed_count:,} fuera"
            
            elif check == 'pattern':
                # Matchea regex
                pattern = rule['pattern']
                mask = df[column].astype(str).str.match(pattern)
                failed_count = (~mask).sum()
                
                result['failed_count'] = failed_count
                result['failed_pct'] = (failed_count / len(df)) * 100
                result['passed'] = failed_count == 0
                result['message'] = f"{'✓' if result['passed'] else '✗'} Pattern: {failed_count:,} no match"
            
            elif check == 'type':
                # Tipo de dato
                expected_type = rule['dtype']
                is_correct_type = df[column].dtype == expected_type
                
                result['passed'] = is_correct_type
                result['message'] = f"{'✓' if result['passed'] else '✗'} Type: {df[column].dtype} (esperado: {expected_type})"
            
            elif check == 'values':
                # Valores permitidos
                allowed = rule['allowed']
                mask = df[column].isin(allowed)
                failed_count = (~mask).sum()
                
                result['failed_count'] = failed_count
                result['failed_pct'] = (failed_count / len(df)) * 100
                result['passed'] = failed_count == 0
                result['message'] = f"{'✓' if result['passed'] else '✗'} Valores permitidos: {failed_count:,} inválidos"
            
            elif check == 'custom':
                # Query custom
                query = rule['query']
                mask = df.query(query).index
                passed_count = len(mask)
                
                result['passed'] = passed_count == len(df)
                result['failed_count'] = len(df) - passed_count
                result['failed_pct'] = (result['failed_count'] / len(df)) * 100
                result['message'] = f"{'✓' if result['passed'] else '✗'} Custom: {result['failed_count']:,} failed"
            
        except Exception as e:
            result['message'] = f"✗ Error: {str(e)}"
        
        return result
    
    def _generate_quality_report(self, df: pd.DataFrame, results: List[Dict], passed: int, failed: int) -> str:
        """Genera reporte de calidad"""
        
        total = passed + failed
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        result = f"""{'✅' if failed == 0 else '⚠️ '} **Reporte de Calidad de Datos**

📊 **Dataset:**
  - Filas: {len(df):,}
  - Columnas: {len(df.columns)}

🔍 **Validaciones:**
  - Total: {total}
  - Pasadas: {passed} ({pass_rate:.1f}%)
  - Fallidas: {failed} ({100-pass_rate:.1f}%)

"""
        
        # Agrupar por columna
        by_column = defaultdict(list)
        for r in results:
            by_column[r['column']].append(r)
        
        result += "📋 **Resultados por Columna:**\n\n"
        
        for column, checks in sorted(by_column.items()):
            result += f"**{column}:**\n"
            for check in checks:
                result += f"  {check['message']}\n"
            result += "\n"
        
        # Resumen de problemas
        problems = [r for r in results if not r['passed']]
        if problems:
            result += "⚠️  **Problemas Detectados:**\n"
            for prob in sorted(problems, key=lambda x: x['failed_pct'], reverse=True)[:10]:
                result += f"  • {prob['column']}: {prob['check']} ({prob['failed_count']:,} filas, {prob['failed_pct']:.1f}%)\n"
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PARQUET CONVERT TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class ParquetConvertTool(BaseTool):
    """Convierte entre CSV, JSON, Parquet"""
    
    name = "parquet_convert"
    description = """Convierte archivos entre formatos: CSV ↔ JSON ↔ Parquet ↔ Excel.
    
Ventajas de Parquet:
  ‣ Compresión eficiente (~10x vs CSV)
  ‣ Lectura columnar rápida
  ‣ Schema preservation
  ‣ Compatible con Spark, Dask, etc.
  
Compresión:
  - snappy (default, balance)
  - gzip (máxima compresión)
  - brotli (alta compresión)
  - none (sin compresión)"""
    
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "input_path": ToolParameter(
                name="input_path",
                type="string",
                description="Ruta del archivo de entrada",
                required=True
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta del archivo de salida",
                required=True
            ),
            "compression": ToolParameter(
                name="compression",
                type="string",
                description="Compresión para Parquet: snappy, gzip, brotli, none",
                required=False,
                enum=["snappy", "gzip", "brotli", "none"]
            ),
            "chunk_size": ToolParameter(
                name="chunk_size",
                type="integer",
                description="Procesar en chunks (para archivos grandes)",
                required=False
            )
        }
    
    def execute(
        self,
        input_path: str = None,
        output_path: str = None,
        compression: str = "snappy",
        chunk_size: int = None,
        **kwargs
    ) -> str:
        if not HAS_PANDAS:
            return "[x] Instala: pip install pandas"
        
        input_path = input_path or kwargs.get('input_path')
        output_path = output_path or kwargs.get('output_path')
        compression = compression or kwargs.get('compression', 'snappy')
        chunk_size = chunk_size or kwargs.get('chunk_size')
        
        if not input_path:
            return "[x] Se requiere 'input_path'"
        
        if not output_path:
            return "[x] Se requiere 'output_path'"
        
        try:
            input_file = Path(input_path)
            output_file = Path(output_path)
            
            if not input_file.exists():
                return f"[x] No existe: {input_path}"
            
            # Detectar formatos
            input_format = self._detect_format(input_file)
            output_format = self._detect_format(output_file)
            
            print(f"🔄 Convirtiendo: {input_format.upper()} → {output_format.upper()}")
            
            # Leer archivo de entrada
            start_time = datetime.now()
            
            if chunk_size:
                # Procesamiento por chunks
                return self._convert_chunked(
                    input_file, output_file, input_format, output_format,
                    chunk_size, compression
                )
            else:
                # Procesamiento completo
                df = self._read_file(input_file, input_format)
                
                # Escribir archivo de salida
                self._write_file(df, output_file, output_format, compression)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Estadísticas
            input_size = input_file.stat().st_size
            output_size = output_file.stat().st_size
            compression_ratio = (1 - output_size / input_size) * 100
            
            result = f"""✅ **Conversión Completada**

📥 **Entrada:**
  - Archivo: {input_file.name}
  - Formato: {input_format.upper()}
  - Tamaño: {self._format_bytes(input_size)}

📤 **Salida:**
  - Archivo: {output_file.name}
  - Formato: {output_format.upper()}
  - Tamaño: {self._format_bytes(output_size)}
  - Compresión: {compression if output_format == 'parquet' else 'N/A'}

📊 **Estadísticas:**
  - Filas: {len(df):,}
  - Columnas: {len(df.columns)}
  - Ratio compresión: {compression_ratio:+.1f}%
  - Tiempo: {duration:.2f}s
  - Velocidad: {len(df)/duration:.0f} filas/s

📍 **Guardado en:** {output_file.absolute()}
"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error en conversión: {e}\n\n{traceback.format_exc()}"
    
    def _detect_format(self, file_path: Path) -> str:
        """Detecta formato del archivo"""
        suffix = file_path.suffix.lower()
        
        format_map = {
            '.csv': 'csv',
            '.json': 'json',
            '.parquet': 'parquet',
            '.xlsx': 'excel',
            '.xls': 'excel'
        }
        
        return format_map.get(suffix, 'csv')
    
    def _read_file(self, file_path: Path, format: str) -> pd.DataFrame:
        """Lee archivo según formato"""
        
        if format == 'csv':
            return pd.read_csv(file_path)
        elif format == 'json':
            return pd.read_json(file_path)
        elif format == 'parquet':
            if HAS_PYARROW:
                return pd.read_parquet(file_path)
            else:
                raise ImportError("Instala: pip install pyarrow")
        elif format == 'excel':
            return pd.read_excel(file_path)
        else:
            raise ValueError(f"Formato no soportado: {format}")
    
    def _write_file(self, df: pd.DataFrame, file_path: Path, format: str, compression: str = None):
        """Escribe archivo según formato"""
        
        # Crear directorio si no existe
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == 'csv':
            df.to_csv(file_path, index=False)
        
        elif format == 'json':
            df.to_json(file_path, orient='records', indent=2)
        
        elif format == 'parquet':
            if HAS_PYARROW:
                df.to_parquet(
                    file_path,
                    index=False,
                    compression=compression or 'snappy'
                )
            else:
                raise ImportError("Instala: pip install pyarrow")
        
        elif format == 'excel':
            df.to_excel(file_path, index=False)
        
        else:
            raise ValueError(f"Formato no soportado: {format}")
    
    def _convert_chunked(
        self, 
        input_file: Path, 
        output_file: Path,
        input_format: str,
        output_format: str,
        chunk_size: int,
        compression: str
    ) -> str:
        """Convierte archivo en chunks (para archivos grandes)"""
        
        if output_format != 'parquet':
            return "[x] Procesamiento por chunks solo soportado para salida Parquet"
        
        if not HAS_PYARROW:
            return "[x] Instala: pip install pyarrow"
        
        # Leer en chunks
        chunks_processed = 0
        total_rows = 0
        
        if input_format == 'csv':
            reader = pd.read_csv(input_file, chunksize=chunk_size)
        else:
            return "[x] Procesamiento por chunks solo soportado desde CSV"
        
        # Procesar primer chunk para obtener schema
        first_chunk = next(reader)
        total_rows += len(first_chunk)
        
        # Escribir primer chunk
        pq.write_table(
            pa.Table.from_pandas(first_chunk),
            output_file,
            compression=compression
        )
        chunks_processed += 1
        
        # Procesar resto de chunks
        for chunk in reader:
            total_rows += len(chunk)
            chunks_processed += 1
            
            # Append al archivo Parquet
            pq.write_table(
                pa.Table.from_pandas(chunk),
                output_file,
                compression=compression,
                append=True
            )
            
            if chunks_processed % 10 == 0:
                print(f"  Procesados {chunks_processed} chunks ({total_rows:,} filas)...")
        
        return f"✅ Conversión completada: {chunks_processed} chunks, {total_rows:,} filas"
    
    def _format_bytes(self, bytes_size: int) -> str:
        """Formatea bytes"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} TB"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. TIME SERIES RESAMPLE TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class TimeSeriesResampleTool(BaseTool):
    """Resampling de series temporales"""
    
    name = "time_series_resample"
    description = """Resamplea series temporales a diferentes frecuencias.
    
Operaciones:
  ‣ Upsample: Aumentar frecuencia (ej: diario → horario)
  ‣ Downsample: Reducir frecuencia (ej: horario → diario)
  
Frecuencias:
  - S: Segundos
  - T/min: Minutos
  - H: Horas
  - D: Días
  - W: Semanas
  - M: Meses
  - Q: Trimestres
  - Y: Años
  
Agregaciones:
  - mean, sum, min, max, median
  - first, last
  - count, std, var"""
    
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "data_path": ToolParameter(
                name="data_path",
                type="string",
                description="Ruta del dataset con serie temporal",
                required=True
            ),
            "datetime_column": ToolParameter(
                name="datetime_column",
                type="string",
                description="Nombre de columna datetime",
                required=True
            ),
            "frequency": ToolParameter(
                name="frequency",
                type="string",
                description="Frecuencia objetivo: H, D, W, M, etc.",
                required=True
            ),
            "aggregation": ToolParameter(
                name="aggregation",
                type="string",
                description="Función de agregación: mean, sum, min, max, etc.",
                required=False
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta del archivo de salida",
                required=False
            ),
            "fill_method": ToolParameter(
                name="fill_method",
                type="string",
                description="Método para rellenar gaps: ffill, bfill, interpolate",
                required=False,
                enum=["ffill", "bfill", "interpolate", "none"]
            )
        }
    
    def execute(
        self,
        data_path: str = None,
        datetime_column: str = None,
        frequency: str = None,
        aggregation: str = "mean",
        output_path: str = None,
        fill_method: str = "none",
        **kwargs
    ) -> str:
        if not HAS_PANDAS:
            return "[x] Instala: pip install pandas"
        
        data_path = data_path or kwargs.get('data_path')
        datetime_column = datetime_column or kwargs.get('datetime_column')
        frequency = frequency or kwargs.get('frequency')
        aggregation = aggregation or kwargs.get('aggregation', 'mean')
        output_path = output_path or kwargs.get('output_path')
        fill_method = fill_method or kwargs.get('fill_method', 'none')
        
        if not data_path:
            return "[x] Se requiere 'data_path'"
        
        if not datetime_column:
            return "[x] Se requiere 'datetime_column'"
        
        if not frequency:
            return "[x] Se requiere 'frequency'"
        
        try:
            # Cargar datos
            print(f"📊 Cargando dataset: {data_path}")
            df = pd.read_csv(data_path)
            
            if datetime_column not in df.columns:
                return f"[x] Columna '{datetime_column}' no encontrada"
            
            # Convertir a datetime
            df[datetime_column] = pd.to_datetime(df[datetime_column])
            
            # Establecer como índice
            df.set_index(datetime_column, inplace=True)
            
            # Ordenar por índice
            df.sort_index(inplace=True)
            
            original_freq = df.index.inferred_freq or "Unknown"
            original_rows = len(df)
            
            print(f"🔄 Resampleando: {original_freq} → {frequency}")
            
            # Resamplear
            if aggregation == "mean":
                df_resampled = df.resample(frequency).mean()
            elif aggregation == "sum":
                df_resampled = df.resample(frequency).sum()
            elif aggregation == "min":
                df_resampled = df.resample(frequency).min()
            elif aggregation == "max":
                df_resampled = df.resample(frequency).max()
            elif aggregation == "median":
                df_resampled = df.resample(frequency).median()
            elif aggregation == "first":
                df_resampled = df.resample(frequency).first()
            elif aggregation == "last":
                df_resampled = df.resample(frequency).last()
            elif aggregation == "count":
                df_resampled = df.resample(frequency).count()
            elif aggregation == "std":
                df_resampled = df.resample(frequency).std()
            elif aggregation == "var":
                df_resampled = df.resample(frequency).var()
            else:
                df_resampled = df.resample(frequency).agg(aggregation)
            
            # Rellenar gaps si es necesario
            if fill_method == "ffill":
                df_resampled = df_resampled.fillna(method='ffill')
            elif fill_method == "bfill":
                df_resampled = df_resampled.fillna(method='bfill')
            elif fill_method == "interpolate":
                df_resampled = df_resampled.interpolate(method='linear')
            
            # Resetear índice
            df_resampled.reset_index(inplace=True)
            
            # Guardar
            if not output_path:
                input_file = Path(data_path)
                output_path = input_file.parent / f"{input_file.stem}_resampled_{frequency}.csv"
            
            output_file = Path(output_path)
            df_resampled.to_csv(output_file, index=False)
            
            # Estadísticas
            result = f"""✅ **Serie Temporal Resampleada**

📊 **Dataset Original:**
  - Archivo: {Path(data_path).name}
  - Filas: {original_rows:,}
  - Frecuencia: {original_freq}
  - Periodo: {df.index.min()} → {df.index.max()}
  - Duración: {df.index.max() - df.index.min()}

🔄 **Resampling:**
  - Frecuencia objetivo: {frequency}
  - Agregación: {aggregation}
  - Fill method: {fill_method}

📈 **Dataset Resampleado:**
  - Filas: {len(df_resampled):,}
  - Periodo: {df_resampled[datetime_column].min()} → {df_resampled[datetime_column].max()}
  - Ratio: {original_rows/len(df_resampled):.2f}x {'reducción' if original_rows > len(df_resampled) else 'aumento'}

💾 **Guardado en:** {output_file.absolute()}
"""
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error resampleando: {e}\n\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DATA ANONYMIZE TOOL
# ═══════════════════════════════════════════════════════════════════════════════

class DataAnonymizeTool(BaseTool):
    """Anonimiza datos sensibles (GDPR-compliant)"""
    
    name = "data_anonymize"
    description = """Anonimiza datos personales para cumplir GDPR.
    
Técnicas:
  ‣ Masking: Ocultar parcialmente (ej: email, teléfono)
  ‣ Hashing: Hash irreversible (SHA-256)
  ‣ Generalization: Rangos/categorías (edad → grupo etario)
  ‣ Suppression: Eliminar valores
  ‣ Fake: Generar datos falsos (Faker)
  ‣ Encryption: Cifrado reversible (AES)
  
Configuración JSON:
```json
{
  "anonymizations": [
    {"column": "email", "method": "mask", "keep_domain": true},
    {"column": "phone", "method": "mask", "visible_digits": 3},
    {"column": "ssn", "method": "hash"},
    {"column": "name", "method": "fake", "type": "name"}
  ]
}
```"""
    
    category = "data"
    
    @property
    def parameters(self) -> Dict[str, ToolParameter]:
        return {
            "data_path": ToolParameter(
                name="data_path",
                type="string",
                description="Ruta del dataset a anonimizar",
                required=True
            ),
            "config_path": ToolParameter(
                name="config_path",
                type="string",
                description="Ruta del archivo de configuración JSON",
                required=False
            ),
            "config_json": ToolParameter(
                name="config_json",
                type="string",
                description="Configuración en formato JSON string",
                required=False
            ),
            "output_path": ToolParameter(
                name="output_path",
                type="string",
                description="Ruta del dataset anonimizado",
                required=False
            ),
            "auto_detect": ToolParameter(
                name="auto_detect",
                type="boolean",
                description="Detectar automáticamente columnas sensibles",
                required=False
            )
        }
    
    def execute(
        self,
        data_path: str = None,
        config_path: str = None,
        config_json: str = None,
        output_path: str = None,
        auto_detect: bool = False,
        **kwargs
    ) -> str:
        if not HAS_PANDAS:
            return "[x] Instala: pip install pandas"
        
        data_path = data_path or kwargs.get('data_path')
        config_path = config_path or kwargs.get('config_path')
        config_json = config_json or kwargs.get('config_json')
        output_path = output_path or kwargs.get('output_path')
        auto_detect = kwargs.get('auto_detect', auto_detect)
        
        if not data_path:
            return "[x] Se requiere 'data_path'"
        
        try:
            # Cargar datos
            print(f"📊 Cargando dataset: {data_path}")
            df = pd.read_csv(data_path)
            
            # Cargar configuración
            if config_path:
                with open(config_path) as f:
                    config = json.load(f)
            elif config_json:
                config = json.loads(config_json)
            elif auto_detect:
                # Auto-detectar columnas sensibles
                config = self._auto_detect_sensitive(df)
            else:
                return "[x] Se requiere 'config_path', 'config_json' o 'auto_detect=true'"
            
            anonymizations = config.get('anonymizations', [])
            
            print(f"🔒 Aplicando {len(anonymizations)} anonimizaciones...")
            
            # Aplicar anonimizaciones
            df_anon = df.copy()
            log = []
            
            for anon in anonymizations:
                column = anon['column']
                method = anon['method']
                
                if column not in df_anon.columns:
                    log.append(f"⚠️  Columna '{column}' no encontrada")
                    continue
                
                df_anon[column], msg = self._anonymize_column(df_anon[column], anon)
                log.append(msg)
            
            # Guardar
            if not output_path:
                input_file = Path(data_path)
                output_path = input_file.parent / f"{input_file.stem}_anonymized.csv"
            
            output_file = Path(output_path)
            df_anon.to_csv(output_file, index=False)
            
            # Resultado
            result = f"""✅ **Datos Anonimizados**

📊 **Dataset:**
  - Filas: {len(df):,}
  - Columnas: {len(df.columns)}

🔒 **Anonimizaciones Aplicadas:**
"""
            
            for msg in log:
                result += f"  {msg}\n"
            
            result += f"\n💾 **Guardado en:** {output_file.absolute()}"
            
            return result
            
        except Exception as e:
            import traceback
            return f"[x] Error anonimizando: {e}\n\n{traceback.format_exc()}"
    
    def _auto_detect_sensitive(self, df: pd.DataFrame) -> Dict:
        """Auto-detecta columnas sensibles"""
        
        anonymizations = []
        
        # Patrones de nombres de columnas sensibles
        sensitive_patterns = {
            r'email': {'method': 'mask', 'keep_domain': True},
            r'phone|tel': {'method': 'mask', 'visible_digits': 3},
            r'ssn|social': {'method': 'hash'},
            r'(first|last)?_?name': {'method': 'fake', 'type': 'name'},
            r'address': {'method': 'fake', 'type': 'address'},
            r'credit|card': {'method': 'mask', 'visible_digits': 4},
            r'ip': {'method': 'hash'},
            r'password|passwd': {'method': 'suppression'}
        }
        
        for col in df.columns:
            col_lower = col.lower()
            
            for pattern, config in sensitive_patterns.items():
                if re.search(pattern, col_lower):
                    anonymizations.append({
                        'column': col,
                        **config
                    })
                    break
        
        return {'anonymizations': anonymizations}
    
    def _anonymize_column(self, series: pd.Series, config: Dict) -> Tuple[pd.Series, str]:
        """Anonimiza una columna"""
        
        column = config['column']
        method = config['method']
        
        if method == 'mask':
            # Masking
            keep_domain = config.get('keep_domain', False)
            visible_digits = config.get('visible_digits', 3)
            
            def mask_value(val):
                if pd.isna(val):
                    return val
                
                val_str = str(val)
                
                if '@' in val_str and keep_domain:
                    # Email: mask username
                    username, domain = val_str.split('@')
                    if len(username) > visible_digits:
                        masked = username[:visible_digits] + '*' * (len(username) - visible_digits)
                    else:
                        masked = '*' * len(username)
                    return f"{masked}@{domain}"
                else:
                    # General: mostrar solo últimos dígitos
                    if len(val_str) > visible_digits:
                        return '*' * (len(val_str) - visible_digits) + val_str[-visible_digits:]
                    else:
                        return '*' * len(val_str)
            
            return series.apply(mask_value), f"✓ {column}: Masked (visible: {visible_digits})"
        
        elif method == 'hash':
            # Hashing
            def hash_value(val):
                if pd.isna(val):
                    return val
                return hashlib.sha256(str(val).encode()).hexdigest()
            
            return series.apply(hash_value), f"✓ {column}: Hashed (SHA-256)"
        
        elif method == 'generalization':
            # Generalización (ej: edad → grupos)
            bins = config.get('bins', [0, 18, 30, 50, 100])
            labels = config.get('labels', ['<18', '18-30', '30-50', '50+'])
            
            generalized = pd.cut(series, bins=bins, labels=labels)
            return generalized, f"✓ {column}: Generalized ({len(labels)} groups)"
        
        elif method == 'suppression':
            # Supresión
            return pd.Series([None] * len(series)), f"✓ {column}: Suppressed"
        
        elif method == 'fake':
            # Datos falsos con Faker
            if not HAS_FAKER:
                return series, f"✗ {column}: Faker no disponible (pip install faker)"
            
            fake = Faker()
            fake_type = config.get('type', 'name')
            
            def generate_fake(val):
                if pd.isna(val):
                    return val
                
                if fake_type == 'name':
                    return fake.name()
                elif fake_type == 'email':
                    return fake.email()
                elif fake_type == 'address':
                    return fake.address()
                elif fake_type == 'phone':
                    return fake.phone_number()
                elif fake_type == 'company':
                    return fake.company()
                else:
                    return fake.word()
            
            return series.apply(generate_fake), f"✓ {column}: Fake ({fake_type})"
        
        else:
            return series, f"✗ {column}: Método '{method}' no soportado"


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'DataProfilerTool',
    'ETLPipelineTool',
    'DataQualityCheckTool',
    'ParquetConvertTool',
    'TimeSeriesResampleTool',
    'DataAnonymizeTool'
]
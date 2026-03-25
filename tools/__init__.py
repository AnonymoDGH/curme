# tools/__init__.py
# ═══════════════════════════════════════════════════════════════════════════════
# NVIDIA CODE - Tools Registry
# Registro de todas las herramientas disponibles
# ═══════════════════════════════════════════════════════════════════════════════

from .base import BaseTool, ToolRegistry, ToolParameter

# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS BASE (siempre disponibles)
# Se importan con fallback individual para máxima resiliencia
# ═══════════════════════════════════════════════════════════════════════════════

# 📁 Archivos base
try:
    from .file_tools import ReadFileTool, WriteFileTool, EditFileTool, DeleteFileTool
except ImportError as e:
    print(f"⚠️  file_tools no disponible: {e}")
    ReadFileTool = WriteFileTool = EditFileTool = DeleteFileTool = None

# ⚡ Terminal
try:
    from .terminal_tools import ExecuteCommandTool
except ImportError as e:
    print(f"⚠️  terminal_tools no disponible: {e}")
    ExecuteCommandTool = None

# 🔍 Búsqueda (mejoradas: ahora incluyen DuplicateFinderTool)
try:
    from .search_tools import (
        SearchFilesTool, SearchInFilesTool, ListDirectoryTool
    )
except ImportError as e:
    print(f"⚠️  search_tools no disponible: {e}")
    SearchFilesTool = SearchInFilesTool = ListDirectoryTool = None

# 🔀 Git (mejoradas: 8 herramientas especializadas reemplazan GitOperationTool)
try:
    from .git_tools import (
        GitStatusTool, GitLogTool, GitDiffTool, GitCommitTool,
        GitBranchTool, GitStashTool, GitRemoteTool, GitTagTool,
    )
    _GIT_TOOLS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  git_tools no disponible: {e}")
    GitStatusTool = GitLogTool = GitDiffTool = GitCommitTool = None
    GitBranchTool = GitStashTool = GitRemoteTool = GitTagTool = None
    _GIT_TOOLS_AVAILABLE = False

# 📦 Proyecto
try:
    from .project_tools import CreateProjectTool, CreateDirectoryTool
except ImportError as e:
    print(f"⚠️  project_tools no disponible: {e}")
    CreateProjectTool = CreateDirectoryTool = None


# ═══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS OPCIONALES
# Cada bloque tiene try/except para no romper si falta algún módulo
# ═══════════════════════════════════════════════════════════════════════════════

OPTIONAL_TOOLS = []


# ⚡ Terminal auxiliares
try:
    from .terminal_tools import ReadCommandOutputTool, CommandExistsTool, GetEnvironmentTool
    OPTIONAL_TOOLS.extend([
        ReadCommandOutputTool(),
        CommandExistsTool(),
        GetEnvironmentTool(),
    ])
except (ImportError, AttributeError):
    pass

# 📁 Archivos avanzados
try:
    from .advanced_file_tools import (
        BatchFileOperationTool, FileWatcherTool,
        EnhancedFileDiffTool, FileEncryptTool, FileMetadataTool
    )
    OPTIONAL_TOOLS.extend([
        BatchFileOperationTool(), FileWatcherTool(),
        EnhancedFileDiffTool(), FileEncryptTool(), FileMetadataTool()
    ])
except (ImportError, Exception):
    pass

# 🧠 SAGE Memory
try:
    from .sage_memory_tools import (
        SAGEInitTool, SAGELoadContextsTool, SAGEReadLatestBlockTool,
        SAGEWriteContextBlockTool, SAGERequestArchiveTool,
        SAGEApplyArchiveTool, SAGERequestMegaArchiveTool,
        SAGECheckCompressionTool, SAGESearchMemoryTool,
        SAGEMergeContextsTool, SAGEExtractMomentsTool,
        SAGENowLifeboatTool, SAGEContextPushTool,
        SAGEContextPullTool, SAGEGitStatusTool
    )
    OPTIONAL_TOOLS.extend([
        SAGEInitTool(), SAGELoadContextsTool(), SAGEReadLatestBlockTool(),
        SAGEWriteContextBlockTool(), SAGERequestArchiveTool(),
        SAGEApplyArchiveTool(), SAGERequestMegaArchiveTool(),
        SAGECheckCompressionTool(), SAGESearchMemoryTool(),
        SAGEMergeContextsTool(), SAGEExtractMomentsTool(),
        SAGENowLifeboatTool(), SAGEContextPushTool(),
        SAGEContextPullTool(), SAGEGitStatusTool()
    ])
except (ImportError, Exception):
    pass

# 🔍 Búsqueda avanzada
try:
    from .advanced_search_tools import (
        SemanticSearchTool, RegexSearchInFilesTool,
        CodeSymbolSearchTool, DuplicateCodeFinderTool
    )
    OPTIONAL_TOOLS.extend([
        SemanticSearchTool(), RegexSearchInFilesTool(),
        CodeSymbolSearchTool(), DuplicateCodeFinderTool()
    ])
except (ImportError, Exception):
    pass

# 🔍 DuplicateFinderTool (nuevo en search_tools mejorado)
try:
    from .search_tools import DuplicateFinderTool
    OPTIONAL_TOOLS.append(DuplicateFinderTool())
except (ImportError, Exception):
    pass

# 🧪 Testing
try:
    from .testing_tools import TestRunTool, TestGenerateTool, LintCheckTool
    OPTIONAL_TOOLS.extend([TestRunTool(), TestGenerateTool(), LintCheckTool()])
except (ImportError, Exception):
    pass

try:
    from .testing_tools_advanced import CoverageReportTool, LoadTestTool
    OPTIONAL_TOOLS.extend([CoverageReportTool(), LoadTestTool()])
except (ImportError, Exception):
    pass

# 💾 Base de datos
try:
    from .database_tools import (
        DatabaseQueryTool, DatabaseSchemaTool,
        DatabaseMigrationTool, DatabaseBackupTool
    )
    OPTIONAL_TOOLS.extend([
        DatabaseQueryTool(), DatabaseSchemaTool(),
        DatabaseMigrationTool(), DatabaseBackupTool()
    ])
except (ImportError, Exception):
    pass

# 🌐 Web & API
try:
    from .web_api_tools import (
        WebSocketTestTool, GraphQLQueryTool,
        APIDocGeneratorTool, CORSTestTool, SSLCertificateTool
    )
    OPTIONAL_TOOLS.extend([
        WebSocketTestTool(), GraphQLQueryTool(),
        APIDocGeneratorTool(), CORSTestTool(), SSLCertificateTool()
    ])
except (ImportError, Exception):
    pass

# 📊 Procesamiento de datos (mejorado: XMLToJSONTool → FormatConverterTool)
try:
    from .data_processing_tools import (
        CSVTransformTool, DataValidatorTool, DataVisualizationTool
    )
    OPTIONAL_TOOLS.extend([
        CSVTransformTool(), DataValidatorTool(), DataVisualizationTool()
    ])
except (ImportError, Exception):
    pass

# FormatConverterTool reemplaza a XMLToJSONTool
try:
    from .data_processing_tools import FormatConverterTool
    OPTIONAL_TOOLS.append(FormatConverterTool())
except (ImportError, Exception):
    # Fallback: intentar con el nombre antiguo
    try:
        from .data_processing_tools import XMLToJSONTool
        OPTIONAL_TOOLS.append(XMLToJSONTool())
    except (ImportError, Exception):
        pass

# 🎨 Media
try:
    from .media_processing_tools import (
        ImageCompressTool, VideoThumbnailTool, PDFMergeSplitTool,
        AudioTranscribeTool, QRGeneratorTool, OCRExtractTool
    )
    OPTIONAL_TOOLS.extend([
        ImageCompressTool(), VideoThumbnailTool(), PDFMergeSplitTool(),
        AudioTranscribeTool(), QRGeneratorTool(), OCRExtractTool()
    ])
except (ImportError, Exception):
    pass

# 🤖 Machine Learning
try:
    from .ml_tools import (
        MLModelTrainTool, MLModelEvaluateTool, DataPreprocessTool,
        ModelDeployServeTool, MLExperimentTrackTool, LLMFineTuneTool
    )
    OPTIONAL_TOOLS.extend([
        MLModelTrainTool(), MLModelEvaluateTool(), DataPreprocessTool(),
        ModelDeployServeTool(), MLExperimentTrackTool(), LLMFineTuneTool()
    ])
except (ImportError, Exception):
    pass

# 📊 Data avanzado
try:
    from .data_advanced_tools import (
        DataProfilerTool, ETLPipelineTool, DataQualityCheckTool,
        ParquetConvertTool, TimeSeriesResampleTool, DataAnonymizeTool
    )
    OPTIONAL_TOOLS.extend([
        DataProfilerTool(), ETLPipelineTool(), DataQualityCheckTool(),
        ParquetConvertTool(), TimeSeriesResampleTool(), DataAnonymizeTool()
    ])
except (ImportError, Exception):
    pass

# 🔒 Seguridad
try:
    from .security_tools import (
        SecretsDetectorTool, HashGeneratorTool,
        JWTDecoderTool, PermissionsCheckTool
    )
    OPTIONAL_TOOLS.extend([
        SecretsDetectorTool(), HashGeneratorTool(),
        JWTDecoderTool(), PermissionsCheckTool()
    ])
except (ImportError, Exception):
    pass

# ⚙️ DevOps
try:
    from .devops_tools import NetworkScanTool, CronSchedulerTool
    OPTIONAL_TOOLS.extend([NetworkScanTool(), CronSchedulerTool()])
except (ImportError, Exception):
    pass

# 🔧 Git avanzado
try:
    from .git_advanced_tools import (
        GitBlameTool, GitStatsTool,
        GitConflictResolverTool, GitBisectTool
    )
    OPTIONAL_TOOLS.extend([
        GitBlameTool(), GitStatsTool(),
        GitConflictResolverTool(), GitBisectTool()
    ])
except (ImportError, Exception):
    pass

# 🏗️ Generación de código (mejorado: mismos nombres de clase)
try:
    from .code_generation_tools import (
        ScaffoldTool, ModelGeneratorTool,
        APIEndpointGeneratorTool, DocstringGeneratorTool
    )
    OPTIONAL_TOOLS.extend([
        ScaffoldTool(), ModelGeneratorTool(),
        APIEndpointGeneratorTool(), DocstringGeneratorTool()
    ])
except (ImportError, Exception):
    pass

# 📝 Documentación
try:
    from .documentation_tools import (
        MarkdownToHTMLTool, ChangelogGeneratorTool, APIDocumentationTool
    )
    OPTIONAL_TOOLS.extend([
        MarkdownToHTMLTool(), ChangelogGeneratorTool(), APIDocumentationTool()
    ])
except (ImportError, Exception):
    pass

# 🔨 Sandbox
try:
    from .sandbox import RunCodeTool, RunFileAndFixTool
    OPTIONAL_TOOLS.extend([RunCodeTool(), RunFileAndFixTool()])
except (ImportError, Exception):
    pass

# 🔬 Análisis
try:
    from .analysis_tools import AnalyzeCodeTool, ThinkDeeplyTool
    OPTIONAL_TOOLS.extend([AnalyzeCodeTool(), ThinkDeeplyTool()])
except (ImportError, Exception):
    pass

# 🔀 Diff (mejorado: ahora incluye MergeTool y SemanticDiffTool)
try:
    from .diff_tools import DiffTool, PatchTool
    OPTIONAL_TOOLS.extend([DiffTool(), PatchTool()])
except (ImportError, Exception):
    pass

# Nuevas herramientas de diff
try:
    from .diff_tools import MergeTool, SemanticDiffTool
    OPTIONAL_TOOLS.extend([MergeTool(), SemanticDiffTool()])
except (ImportError, Exception):
    pass

# 🌐 HTTP
try:
    from .http_tools import HTTPRequestTool
    OPTIONAL_TOOLS.append(HTTPRequestTool())
except (ImportError, Exception):
    pass

# 🧠 Memory
try:
    from .memory_tools import (
        MemoryStoreTool, MemoryRecallTool,
        MemorySearchTool, MemoryListTool
    )
    OPTIONAL_TOOLS.extend([
        MemoryStoreTool(), MemoryRecallTool(),
        MemorySearchTool(), MemoryListTool()
    ])
except (ImportError, Exception):
    pass

# 🌐 Web scraping
try:
    from .web_tools import (
        WebScrapeTool, WebSearchTool,
        DownloadFileTool, GitHubAPITool
    )
    OPTIONAL_TOOLS.extend([
        WebScrapeTool(), WebSearchTool(),
        DownloadFileTool(), GitHubAPITool()
    ])
except (ImportError, Exception):
    pass

# 📋 Data tools
try:
    from .data_tools import (
        JsonProcessTool, CsvProcessTool,
        RegexTool, TextTransformTool
    )
    OPTIONAL_TOOLS.extend([
        JsonProcessTool(), CsvProcessTool(),
        RegexTool(), TextTransformTool()
    ])
except (ImportError, Exception):
    pass

# 💻 System
try:
    from .system_tools import (
        SystemInfoTool, PortCheckTool, ProcessListTool,
        EnvManageTool, DiskUsageTool
    )
    OPTIONAL_TOOLS.extend([
        SystemInfoTool(), PortCheckTool(), ProcessListTool(),
        EnvManageTool(), DiskUsageTool()
    ])
except (ImportError, Exception):
    pass

# 🤖 AI
try:
    from .ai_tools import ConsultAITool, MultiAIConsultTool
    OPTIONAL_TOOLS.extend([ConsultAITool(), MultiAIConsultTool()])
except (ImportError, Exception):
    pass

# 🖥️ Computer
try:
    from .computer_tools import (
        ComputerActionTool, ComputerMultiStepTool,
        DirectClickTool, DirectTypeTool, DirectKeyTool,
        RunCommandTool, LaunchAppTool, WaitTool
    )
    OPTIONAL_TOOLS.extend([
        ComputerActionTool(), ComputerMultiStepTool(),
        DirectClickTool(), DirectTypeTool(), DirectKeyTool(),
        RunCommandTool(), LaunchAppTool(), WaitTool(),
    ])
except (ImportError, Exception):
    pass

# 🎮 Minecraft
try:
    from .minecraft_tools import MinecraftTool
    OPTIONAL_TOOLS.append(MinecraftTool())
except (ImportError, Exception):
    pass

# 🔥 Arsenal Agresivo
try:
    from .arsenal_tools import (
        ScrapingAgresivoTool, LLMSlaveTool, OSINTDoxTool,
        PentestExploitTool, CloneFrontendTool
    )
    OPTIONAL_TOOLS.extend([
        ScrapingAgresivoTool(), LLMSlaveTool(), OSINTDoxTool(),
        PentestExploitTool(), CloneFrontendTool()
    ])
except (ImportError, Exception):
    pass

# 📸 Screenshots y Media
try:
    from .screenshot_tool import ScreenshotWebTool, SendMediaTool, ScreenshotLocalTool
    OPTIONAL_TOOLS.extend([
        ScreenshotWebTool(), SendMediaTool(), ScreenshotLocalTool()
    ])
except (ImportError, Exception) as e:
    print(f"⚠️  screenshot_tool no disponible: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRO DE HERRAMIENTAS
# ═══════════════════════════════════════════════════════════════════════════════

def register_all_tools():
    """Registra todas las herramientas disponibles en el ToolRegistry."""

    # ── Herramientas base ─────────────────────────────────────────────────
    base_tools = []

    # Archivos
    for tool_class in (ReadFileTool, WriteFileTool, EditFileTool, DeleteFileTool):
        if tool_class is not None:
            base_tools.append(tool_class())

    # Terminal
    if ExecuteCommandTool is not None:
        base_tools.append(ExecuteCommandTool())

    # Búsqueda
    for tool_class in (SearchFilesTool, SearchInFilesTool, ListDirectoryTool):
        if tool_class is not None:
            base_tools.append(tool_class())

    # Git (8 herramientas especializadas)
    if _GIT_TOOLS_AVAILABLE:
        for tool_class in (
            GitStatusTool, GitLogTool, GitDiffTool, GitCommitTool,
            GitBranchTool, GitStashTool, GitRemoteTool, GitTagTool,
        ):
            if tool_class is not None:
                base_tools.append(tool_class())

    # Proyecto
    for tool_class in (CreateProjectTool, CreateDirectoryTool):
        if tool_class is not None:
            base_tools.append(tool_class())

    # ── Combinar base + opcionales ────────────────────────────────────────
    all_tools = base_tools + OPTIONAL_TOOLS

    registered = 0
    failed = 0
    for tool in all_tools:
        try:
            ToolRegistry.register(tool)
            registered += 1
        except Exception as e:
            failed += 1

    if failed > 0:
        print(f"  ⚠️  {failed} herramienta(s) no se pudieron registrar")

    return registered


def get_tools_by_category():
    """Retorna herramientas agrupadas por categoría."""
    categories = {}
    for tool_name, tool in ToolRegistry._tools.items():
        category = getattr(tool, 'category', 'general')
        if category not in categories:
            categories[category] = []
        categories[category].append({
            'name': tool_name,
            'description': tool.description,
            'class': tool.__class__.__name__
        })
    return categories


def print_tools_summary():
    """Imprime resumen de herramientas disponibles."""
    categories = get_tools_by_category()

    print("\n" + "═" * 80)
    print("📦 NVIDIA CODE — Herramientas Disponibles")
    print("═" * 80)

    category_icons = {
        'files': '📁', 'search': '🔍', 'git': '🔀',
        'testing': '🧪', 'database': '💾', 'web': '🌐',
        'data': '📊', 'media': '🎨', 'ml': '🤖',
        'security': '🔒', 'devops': '⚙️', 'system': '💻',
        'computer': '🖥️', 'ai': '🧠', 'minecraft': '🎮',
        'terminal': '⚡', 'general': '📌', 'memory': '🧠',
        'codegen': '🏗️', 'documentation': '📝', 'diff': '🔀',
        'sandbox': '🔨', 'analysis': '🔬', 'sage': '🌿',
    }

    total_tools = 0
    for category, tools in sorted(categories.items()):
        icon = category_icons.get(category, '📌')
        print(f"\n{icon} {category.upper()} ({len(tools)} herramientas)")
        print("─" * 80)
        for tool in sorted(tools, key=lambda x: x['name']):
            desc = tool['description'][:50]
            print(f"  • {tool['name']:30s} {desc}...")
        total_tools += len(tools)

    print("\n" + "═" * 80)
    print(f"  Total: {total_tools} herramientas registradas")
    print("═" * 80 + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-REGISTRO
# ═══════════════════════════════════════════════════════════════════════════════

tool_count = register_all_tools()

__all__ = [
    'BaseTool',
    'ToolRegistry',
    'ToolParameter',
    'register_all_tools',
    'get_tools_by_category',
    'print_tools_summary',
    'tool_count',
    'OPTIONAL_TOOLS',
]
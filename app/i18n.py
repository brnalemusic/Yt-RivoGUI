from __future__ import annotations

import locale
import sys
from typing import Any

TRANSLATIONS: dict[str, dict[str, str]] = {
    'pt_BR': {
        'app_title': 'yt-rivogui',
        'app_subtitle': 'downloader minimalista de mídia',
        'url_placeholder': 'cole a url do vídeo ou playlist aqui...',
        'paste_button': 'colar',
        'clear_button': 'limpar',
        'destination_folder': 'salvar em:',
        'browse_folder': 'procurar',
        'open_folder': 'abrir pasta',
        'preview_loading': 'obtendo metadados...',
        'preview_ready': 'vídeo identificado',
        'preview_empty': 'insira uma url acima para carregar pré-visualização e opções',
        'preview_error': 'não foi possível obter detalhes prévios (o download ainda pode funcionar)',
        'duration_label': 'duração',
        'channel_label': 'canal',
        'views_label': 'views',
        'mode_video': 'vídeo',
        'mode_audio': 'áudio',
        'mode_thumbnail': 'capa',
        'quality_label': 'qualidade:',
        'quality_best': 'melhor disponível (original)',
        'quality_2160p': '4k (2160p)',
        'quality_1440p': '2k (1440p)',
        'quality_1080p': '1080p (full hd)',
        'quality_720p': '720p (hd)',
        'quality_480p': '480p (sd)',
        'quality_360p': '360p (baixa)',
        'format_label': 'contêiner:',
        'audio_format_label': 'codec áudio:',
        'audio_quality_label': 'qualidade áudio:',
        'audio_quality_best': 'melhor bitrate (original)',
        'audio_quality_320': '320 kbps (alta fidelidade)',
        'audio_quality_256': '256 kbps',
        'audio_quality_192': '192 kbps (padrão)',
        'audio_quality_128': '128 kbps',
        'opt_embed_thumbnail': 'embutir capa no arquivo',
        'opt_embed_metadata': 'embutir metadados e capítulos',
        'opt_subtitles': 'baixar legendas',
        'sub_lang_label': 'idioma:',
        'sub_lang_pt': 'português',
        'sub_lang_en': 'inglês',
        'sub_lang_all': 'português + inglês',
        'opt_playlist': 'baixar playlist inteira',
        'playlist_notice': 'vídeos da playlist serão organizados em uma subpasta com o nome da lista.',
        'btn_download': 'iniciar download',
        'btn_downloading': 'baixando...',
        'btn_cancel': 'cancelar',
        'status_ready': 'pronto para download',
        'status_connecting': 'conectando ao servidor...',
        'status_downloading': 'baixando arquivo...',
        'status_processing': 'processando mídias (ffmpeg)...',
        'status_finished': 'download concluído com sucesso!',
        'status_cancelled': 'download cancelado pelo usuário',
        'status_failed': 'falha no download',
        'speed_label': 'velocidade',
        'eta_label': 'tempo restante',
        'size_label': 'tamanho',
        'toggle_logs_show': 'exibir logs [▼]',
        'toggle_logs_hide': 'ocultar logs [▲]',
        'logs_title': 'registro de atividades',
        'alert_no_url': 'insira uma url válida para continuar.',
        'alert_already_running': 'já existe um download em andamento.',
        'open_file': 'abrir arquivo',
        'language_label': 'idioma:',
        'mode_split': 'vídeo + áudio (separados)',
        'opt_video_muted': 'vídeo sem áudio (apenas vídeo)',
        'audio_quality_wav': 'sem perdas (pcm)',
        'notice_wav_thumbnail': 'o formato .wav não suporta capa embutida',
        'status_downloading_split': 'baixando vídeo e áudio...',
        'status_finished_split': 'download de vídeo e áudio concluído com sucesso!',
        'section_source': 'fonte & destino',
        'section_preview': 'mídia detectada',
        'section_options': 'modo & configurações',
        'notice_thumbnail_mode': 'modo capa: apenas a miniatura será salva no diretório selecionado.',
        'progress_label': 'progresso',
        'channel_prefix': 'canal:',
        'duration_prefix': 'tempo:',
        'playlist_prefix': 'playlist:',
        'items_suffix': 'itens',
    },
    'en_US': {
        'app_title': 'yt-rivogui',
        'app_subtitle': 'minimalist smart media downloader',
        'url_placeholder': 'paste video or playlist url here...',
        'paste_button': 'paste',
        'clear_button': 'clear',
        'destination_folder': 'save to:',
        'browse_folder': 'browse',
        'open_folder': 'open folder',
        'preview_loading': 'fetching metadata...',
        'preview_ready': 'video identified',
        'preview_empty': 'paste a url above to load preview and options',
        'preview_error': 'could not fetch preview details (direct download may still work)',
        'duration_label': 'duration',
        'channel_label': 'channel',
        'views_label': 'views',
        'mode_video': 'video',
        'mode_audio': 'audio',
        'mode_thumbnail': 'cover',
        'quality_label': 'quality:',
        'quality_best': 'best available (original)',
        'quality_2160p': '4k (2160p)',
        'quality_1440p': '2k (1440p)',
        'quality_1080p': '1080p (full hd)',
        'quality_720p': '720p (hd)',
        'quality_480p': '480p (sd)',
        'quality_360p': '360p (low)',
        'format_label': 'container:',
        'audio_format_label': 'audio codec:',
        'audio_quality_label': 'audio quality:',
        'audio_quality_best': 'best bitrate (original)',
        'audio_quality_320': '320 kbps (high fidelity)',
        'audio_quality_256': '256 kbps',
        'audio_quality_192': '192 kbps (standard)',
        'audio_quality_128': '128 kbps',
        'opt_embed_thumbnail': 'embed cover art into media',
        'opt_embed_metadata': 'embed metadata and chapters',
        'opt_subtitles': 'download subtitles',
        'sub_lang_label': 'language:',
        'sub_lang_pt': 'portuguese',
        'sub_lang_en': 'english',
        'sub_lang_all': 'portuguese + english',
        'opt_playlist': 'download entire playlist',
        'playlist_notice': 'playlist videos will be saved into a folder named after the playlist.',
        'btn_download': 'start download',
        'btn_downloading': 'downloading...',
        'btn_cancel': 'cancel',
        'status_ready': 'ready to download',
        'status_connecting': 'connecting to server...',
        'status_downloading': 'downloading file...',
        'status_processing': 'processing media (ffmpeg)...',
        'status_finished': 'download completed successfully!',
        'status_cancelled': 'download cancelled by user',
        'status_failed': 'download failed',
        'speed_label': 'speed',
        'eta_label': 'eta',
        'size_label': 'size',
        'toggle_logs_show': 'show logs [▼]',
        'toggle_logs_hide': 'hide logs [▲]',
        'logs_title': 'activity logs',
        'alert_no_url': 'please enter a valid url to continue.',
        'alert_already_running': 'a download is already in progress.',
        'open_file': 'open file',
        'language_label': 'language:',
        'mode_split': 'video + audio (separated)',
        'opt_video_muted': 'video without audio (video only)',
        'audio_quality_wav': 'lossless (pcm)',
        'notice_wav_thumbnail': '.wav format does not support embedded cover art',
        'status_downloading_split': 'downloading video and audio...',
        'status_finished_split': 'video and audio downloaded successfully!',
        'section_source': 'source & destination',
        'section_preview': 'detected media',
        'section_options': 'mode & settings',
        'notice_thumbnail_mode': 'cover mode: only thumbnail image will be saved to the chosen folder.',
        'progress_label': 'progress',
        'channel_prefix': 'channel:',
        'duration_prefix': 'duration:',
        'playlist_prefix': 'playlist:',
        'items_suffix': 'items',
    }
}


def detect_system_language() -> str:
    """
    Detects system language:
    - If Portuguese (any country/variant: pt_BR, pt_PT, etc.), returns 'pt_BR'.
    - For any other language, returns 'en_US'.
    """
    try:
        if sys.platform == 'win32':
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            if lang_id == 0x16:  # LANG_PORTUGUESE
                return 'pt_BR'

        loc, _ = locale.getlocale()
        if not loc:
            loc = locale.getdefaultlocale()[0]
        if loc and loc.lower().startswith('pt'):
            return 'pt_BR'
    except Exception:
        pass

    return 'en_US'


class I18nManager:
    def __init__(self, default_lang: str | None = None):
        self.current_lang = default_lang or detect_system_language()
        if self.current_lang not in TRANSLATIONS:
            self.current_lang = 'en_US'

    def set_language(self, lang: str):
        if lang in TRANSLATIONS:
            self.current_lang = lang

    def get(self, key: str, **kwargs: Any) -> str:
        lang_dict = TRANSLATIONS.get(self.current_lang, TRANSLATIONS['en_US'])
        text = lang_dict.get(key, TRANSLATIONS['en_US'].get(key, key))
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def __call__(self, key: str, **kwargs: Any) -> str:
        return self.get(key, **kwargs)

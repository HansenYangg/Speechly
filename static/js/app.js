let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;
        let currentLanguage = 'en';
        let recordedBlob = null;
        let recordings = [];
        let sessionId = null;
        let feedbackEventSource = null;
        let recordingStartTime = null;
        let recordingTimerInterval = null;

        // Use current host for API calls (works for both local and production)
        const API_BASE = window.location.origin + '/api';

        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            initializeSession();
            setupKeyboardShortcuts();
            loadLanguages();
            checkHealth();
            setupBeforeUnload();
        });

        async function initializeSession() {
            try {
                const response = await fetch(API_BASE + '/session/new', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const result = await response.json();
                if (result.success) {
                    sessionId = result.session_id;
                    document.getElementById('sessionId').textContent = sessionId.substring(0, 8) + '...';
                    console.log('Session initialized:', sessionId);
                } else {
                    throw new Error('Failed to create session');
                }
            } catch (error) {
                console.error('Failed to initialize session:', error);
                sessionId = generateUUID();
                document.getElementById('sessionId').textContent = sessionId.substring(0, 8) + '... (offline)';
            }
        }

        function setupBeforeUnload() {
            window.addEventListener('beforeunload', function(e) {
                if (sessionId) {
                    clearAllRecordings();
                    cleanupSession();
                }
                if (feedbackEventSource) {
                    feedbackEventSource.close();
                }
            });
            
            window.addEventListener('unload', function(e) {
                if (sessionId) {
                    clearAllRecordings();
                    cleanupSession();
                }
                if (feedbackEventSource) {
                    feedbackEventSource.close();
                }
            });
        }

        async function clearAllRecordings() {
            if (!sessionId) return;
            
            try {
                await fetch(API_BASE + '/recordings', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    }
                });
            } catch (error) {
                console.log('Failed to clear recordings on page unload');
            }
        }

        async function cleanupSession() {
            if (!sessionId) return;
            
            try {
                await fetch(API_BASE + '/session/cleanup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    }
                });
            } catch (error) {
                console.log('Failed to cleanup session');
            }
        }

        const translations = {
            en: {
                title: "AI Speech Evaluator",
                subtitle: "Transform your speaking skills with cutting-edge AI-powered feedback and analysis",
                sessionText: "Your Session:",
                languageLabel: "Choose your target language:",
                languageSection: "Language Selection",
                actionsSection: "Quick Actions",
                recordBtn: "Record Speech (R)",
                viewBtn: "View Recordings (L)",
                stopBtn: "Stop Recording (Enter)",
                setupSection: "Recording Setup",
                topicLabel: "Speech Topic",
                topicPlaceholder: "What will you be speaking about?",
                typeLabel: "Speech Type",
                typePlaceholder: "e.g., interview, presentation, debate",
                repeatLabel: "This is a repeat attempt on the same topic",
                startBtn: "Start Recording (T)",
                cancelBtn: "Cancel (B)",
                recordingText: "Recording in Progress",
                recordingSubtext: "Speak clearly into your microphone. Click stop when finished or cancel to discard.",
                cancelActiveBtn: "Cancel (X)",
                recordingsSection: "Your Recordings",
                feedbackSection: "AI Feedback & Analysis",
                transcriptionSection: "Speech Transcription",
                playbackSection: "Recording Playback",
                noRecordings: "No recordings found",
                noRecordingsSubtext: "Create your first recording to get started!",
                playRecBtn: "Play",
                deleteBtn: "Delete",
                recordingTooShort: "Recording Too Short",
                recordingTooShortText: "Sorry! The recording was too short to generate feedback for. Please try again with a longer speech.",
                aiAnalyzing: "AI is analyzing your speech"
            },
            es: {
                title: "Evaluador de Discursos IA",
                subtitle: "Transforma tus habilidades de habla con análisis y retroalimentación impulsados por IA de vanguardia",
                sessionText: "Tu Sesión:",
                languageLabel: "Elige tu idioma objetivo:",
                languageSection: "Selección de Idioma",
                actionsSection: "Acciones Rápidas",
                recordBtn: "Grabar Discurso (R)",
                viewBtn: "Ver Grabaciones (L)",
                stopBtn: "Detener Grabación (Enter)",
                setupSection: "Configuración de Grabación",
                topicLabel: "Tema del Discurso",
                topicPlaceholder: "¿De qué vas a hablar?",
                typeLabel: "Tipo de Discurso",
                typePlaceholder: "ej., entrevista, presentación, debate",
                repeatLabel: "Este es un segundo intento del mismo tema",
                startBtn: "Iniciar Grabación (T)",
                cancelBtn: "Cancelar (B)",
                recordingText: "Grabación en Progreso",
                recordingSubtext: "Habla claramente al micrófono. Haz clic en detener cuando termines o cancelar para descartar.",
                cancelActiveBtn: "Cancelar (X)",
                recordingsSection: "Tus Grabaciones",
                feedbackSection: "Análisis y Retroalimentación IA",
                transcriptionSection: "Transcripción del Discurso",
                playbackSection: "Reproducción de Grabación",
                noRecordings: "No se encontraron grabaciones",
                noRecordingsSubtext: "¡Crea tu primera grabación para comenzar!",
                playRecBtn: "Reproducir",
                deleteBtn: "Eliminar",
                recordingTooShort: "Grabación Muy Corta",
                recordingTooShortText: "¡Lo siento! La grabación fue muy corta para generar retroalimentación. Por favor, inténtalo de nuevo con un discurso más largo.",
                aiAnalyzing: "La IA está analizando tu discurso"
            },
            fr: {
                title: "Évaluateur de Discours IA",
                subtitle: "Transformez vos compétences oratoires avec des commentaires et analyses IA de pointe",
                sessionText: "Votre Session:",
                languageLabel: "Choisissez votre langue cible:",
                languageSection: "Sélection de Langue",
                actionsSection: "Actions Rapides",
                recordBtn: "Enregistrer Discours (R)",
                viewBtn: "Voir Enregistrements (L)",
                stopBtn: "Arrêter Enregistrement (Entrée)",
                setupSection: "Configuration d'Enregistrement",
                topicLabel: "Sujet du Discours",
                topicPlaceholder: "De quoi allez-vous parler?",
                typeLabel: "Type de Discours",
                typePlaceholder: "ex., entretien, présentation, débat",
                repeatLabel: "Ceci est une seconde tentative sur le même sujet",
                startBtn: "Démarrer Enregistrement (T)",
                cancelBtn: "Annuler (B)",
                recordingText: "Enregistrement en Cours",
                recordingSubtext: "Parlez clairement dans votre microphone. Cliquez arrêter quand terminé ou annuler pour ignorer.",
                cancelActiveBtn: "Annuler (X)",
                recordingsSection: "Vos Enregistrements",
                feedbackSection: "Analyse et Commentaires IA",
                transcriptionSection: "Transcription du Discours",
                playbackSection: "Lecture d'Enregistrement",
                noRecordings: "Aucun enregistrement trouvé",
                noRecordingsSubtext: "Créez votre premier enregistrement pour commencer!",
                playRecBtn: "Lire",
                deleteBtn: "Supprimer",
                recordingTooShort: "Enregistrement Trop Court",
                recordingTooShortText: "Désolé! L'enregistrement était trop court pour générer des commentaires. Veuillez réessayer avec un discours plus long.",
                aiAnalyzing: "L'IA analyse votre discours"
            },
            de: {
                title: "KI-Sprach-Evaluator",
                subtitle: "Verwandeln Sie Ihre Sprechfähigkeiten mit modernsten KI-gestützten Feedback und Analysen",
                sessionText: "Ihre Sitzung:",
                languageLabel: "Wählen Sie Ihre Zielsprache:",
                languageSection: "Sprachauswahl",
                actionsSection: "Schnelle Aktionen",
                recordBtn: "Rede Aufnehmen (R)",
                viewBtn: "Aufnahmen Anzeigen (L)",
                stopBtn: "Aufnahme Stoppen (Enter)",
                setupSection: "Aufnahme-Einrichtung",
                topicLabel: "Rede-Thema",
                topicPlaceholder: "Worüber werden Sie sprechen?",
                typeLabel: "Rede-Typ",
                typePlaceholder: "z.B., Interview, Präsentation, Debatte",
                repeatLabel: "Dies ist ein zweiter Versuch zum gleichen Thema",
                startBtn: "Aufnahme Starten (T)",
                cancelBtn: "Abbrechen (B)",
                recordingText: "Aufnahme läuft",
                recordingSubtext: "Sprechen Sie deutlich in Ihr Mikrofon. Klicken Sie stoppen wenn fertig oder abbrechen zum Verwerfen.",
                cancelActiveBtn: "Abbrechen (X)",
                recordingsSection: "Ihre Aufnahmen",
                feedbackSection: "KI-Feedback & Analyse",
                transcriptionSection: "Rede-Transkription",
                playbackSection: "Aufnahme-Wiedergabe",
                noRecordings: "Keine Aufnahmen gefunden",
                noRecordingsSubtext: "Erstellen Sie Ihre erste Aufnahme um zu beginnen!",
                playRecBtn: "Abspielen",
                deleteBtn: "Löschen",
                recordingTooShort: "Aufnahme Zu Kurz",
                recordingTooShortText: "Entschuldigung! Die Aufnahme war zu kurz um Feedback zu generieren. Bitte versuchen Sie es erneut mit einer längeren Rede.",
                aiAnalyzing: "KI analysiert Ihre Rede"
            },
            it: {
                title: "Valutatore di Discorsi IA",
                subtitle: "Trasforma le tue abilità oratorie con feedback e analisi all'avanguardia basati sull'IA",
                sessionText: "La Tua Sessione:",
                languageLabel: "Scegli la tua lingua di destinazione:",
                languageSection: "Selezione Lingua",
                actionsSection: "Azioni Rapide",
                recordBtn: "Registra Discorso (R)",
                viewBtn: "Visualizza Registrazioni (L)",
                stopBtn: "Ferma Registrazione (Invio)",
                setupSection: "Configurazione Registrazione",
                topicLabel: "Argomento del Discorso",
                topicPlaceholder: "Di cosa parlerai?",
                typeLabel: "Tipo di Discorso",
                typePlaceholder: "es., intervista, presentazione, dibattito",
                repeatLabel: "Questo è un secondo tentativo sullo stesso argomento",
                startBtn: "Inizia Registrazione (T)",
                cancelBtn: "Annulla (B)",
                recordingText: "Registrazione in Corso",
                recordingSubtext: "Parla chiaramente nel microfono. Clicca ferma quando hai finito o annulla per scartare.",
                cancelActiveBtn: "Annulla (X)",
                recordingsSection: "Le Tue Registrazioni",
                feedbackSection: "Feedback e Analisi IA",
                transcriptionSection: "Trascrizione del Discorso",
                playbackSection: "Riproduzione Registrazione",
                noRecordings: "Nessuna registrazione trovata",
                noRecordingsSubtext: "Crea la tua prima registrazione per iniziare!",
                playRecBtn: "Riproduci",
                deleteBtn: "Elimina",
                recordingTooShort: "Registrazione Troppo Breve",
                recordingTooShortText: "Spiacente! La registrazione era troppo breve per generare feedback. Riprova con un discorso più lungo.",
                aiAnalyzing: "L'IA sta analizzando il tuo discorso"
            },
            pt: {
                title: "Avaliador de Discursos IA",
                subtitle: "Transforme suas habilidades de fala com feedback e análise de ponta baseados em IA",
                sessionText: "Sua Sessão:",
                languageLabel: "Escolha seu idioma alvo:",
                languageSection: "Seleção de Idioma",
                actionsSection: "Ações Rápidas",
                recordBtn: "Gravar Discurso (R)",
                viewBtn: "Ver Gravações (L)",
                stopBtn: "Parar Gravação (Enter)",
                setupSection: "Configuração de Gravação",
                topicLabel: "Tópico do Discurso",
                topicPlaceholder: "Sobre o que você vai falar?",
                typeLabel: "Tipo de Discurso",
                typePlaceholder: "ex., entrevista, apresentação, debate",
                repeatLabel: "Esta é uma segunda tentativa no mesmo tópico",
                startBtn: "Iniciar Gravação (T)",
                cancelBtn: "Cancelar (B)",
                recordingText: "Gravação em Progresso",
                recordingSubtext: "Fale claramente no microfone. Clique parar quando terminar ou cancelar para descartar.",
                cancelActiveBtn: "Cancelar (X)",
                recordingsSection: "Suas Gravações",
                feedbackSection: "Feedback e Análise IA",
                transcriptionSection: "Transcrição do Discurso",
                playbackSection: "Reprodução da Gravação",
                noRecordings: "Nenhuma gravação encontrada",
                noRecordingsSubtext: "Crie sua primeira gravação para começar!",
                playRecBtn: "Reproduzir",
                deleteBtn: "Excluir",
                recordingTooShort: "Gravação Muito Curta",
                recordingTooShortText: "Desculpe! A gravação foi muito curta para gerar feedback. Tente novamente com um discurso mais longo.",
                aiAnalyzing: "A IA está analisando seu discurso"
            },
            ru: {
                title: "ИИ Оценщик Речи",
                subtitle: "Преобразуйте свои навыки речи с помощью передовой обратной связи и анализа на основе ИИ",
                sessionText: "Ваша Сессия:",
                languageLabel: "Выберите целевой язык:",
                languageSection: "Выбор Языка",
                actionsSection: "Быстрые Действия",
                recordBtn: "Записать Речь (R)",
                viewBtn: "Просмотр Записей (L)",
                stopBtn: "Остановить Запись (Enter)",
                setupSection: "Настройка Записи",
                topicLabel: "Тема Речи",
                topicPlaceholder: "О чём вы будете говорить?",
                typeLabel: "Тип Речи",
                typePlaceholder: "напр., интервью, презентация, дебаты",
                repeatLabel: "Это вторая попытка на ту же тему",
                startBtn: "Начать Запись (T)",
                cancelBtn: "Отмена (B)",
                recordingText: "Запись в Процессе",
                recordingSubtext: "Говорите чётко в микрофон. Нажмите стоп когда закончите или отмена для отмены.",
                cancelActiveBtn: "Отмена (X)",
                recordingsSection: "Ваши Записи",
                feedbackSection: "ИИ Обратная Связь и Анализ",
                transcriptionSection: "Транскрипция Речи",
                playbackSection: "Воспроизведение Записи",
                noRecordings: "Записи не найдены",
                noRecordingsSubtext: "Создайте первую запись для начала!",
                playRecBtn: "Воспроизвести",
                deleteBtn: "Удалить",
                recordingTooShort: "Запись Слишком Короткая",
                recordingTooShortText: "Извините! Запись была слишком короткой для генерации обратной связи. Попробуйте снова с более длинной речью.",
                aiAnalyzing: "ИИ анализирует вашу речь"
            },
             ko: {
                title: "AI 스피치 평가기",
                subtitle: "최첨단 AI 기반 피드백과 분석으로 말하기 실력을 향상시키세요",
                sessionText: "세션:",
                languageLabel: "목표 언어를 선택하세요:",
                languageSection: "언어 선택",
                actionsSection: "빠른 작업",
                recordBtn: "스피치 녹음 (R)",
                viewBtn: "녹음 보기 (L)",
                stopBtn: "녹음 중지 (Enter)",
                setupSection: "녹음 설정",
                topicLabel: "스피치 주제",
                topicPlaceholder: "무엇에 대해 말씀하실 건가요?",
                typeLabel: "스피치 유형",
                typePlaceholder: "예: 면접, 발표, 토론",
                repeatLabel: "같은 주제에 대한 재시도입니다",
                startBtn: "녹음 시작 (T)",
                cancelBtn: "취소 (B)",
                recordingText: "녹음 진행 중",
                recordingSubtext: "마이크에 대고 명확하게 말하세요. 완료되면 중지를 클릭하거나 취소를 클릭하여 삭제하세요.",
                cancelActiveBtn: "취소 (X)",
                recordingsSection: "녹음 목록",
                feedbackSection: "AI 피드백 및 분석",
                transcriptionSection: "스피치 전사",
                playbackSection: "녹음 재생",
                noRecordings: "녹음을 찾을 수 없습니다",
                noRecordingsSubtext: "첫 번째 녹음을 만들어 시작하세요!",
                playRecBtn: "재생",
                deleteBtn: "삭제",
                recordingTooShort: "녹음이 너무 짧습니다",
                recordingTooShortText: "죄송합니다! 녹음이 너무 짧아서 피드백을 생성할 수 없습니다. 더 긴 스피치로 다시 시도해 주세요.",
                aiAnalyzing: "AI가 당신의 스피치를 분석하고 있습니다"
            },
            zh: {
                title: "AI语音评估器",
                subtitle: "用尖端的AI驱动反馈和分析改变您的演讲技能",
                sessionText: "您的会话：",
                languageLabel: "选择您的目标语言：",
                languageSection: "语言选择",
                actionsSection: "快速操作",
                recordBtn: "录制演讲 (R)",
                viewBtn: "查看录音 (L)",
                stopBtn: "停止录制 (Enter)",
                setupSection: "录制设置",
                topicLabel: "演讲主题",
                topicPlaceholder: "您将谈论什么？",
                typeLabel: "演讲类型",
                typePlaceholder: "例如：面试、演示、辩论",
                repeatLabel: "这是同一主题的重复尝试",
                startBtn: "开始录制 (T)",
                cancelBtn: "取消 (B)",
                recordingText: "录制进行中",
                recordingSubtext: "清楚地对着麦克风说话。完成时点击停止或点击取消放弃。",
                cancelActiveBtn: "取消 (X)",
                recordingsSection: "您的录音",
                feedbackSection: "AI反馈与分析",
                transcriptionSection: "演讲转录",
                playbackSection: "录音播放",
                noRecordings: "未找到录音",
                noRecordingsSubtext: "创建您的第一个录音开始吧！",
                playRecBtn: "播放",
                deleteBtn: "删除",
                recordingTooShort: "录音太短",
                recordingTooShortText: "抱歉！录音太短无法生成反馈。请用更长的演讲重试。",
                aiAnalyzing: "AI正在分析您的演讲"
            },
            ja: {
                title: "AIスピーチ評価器",
                subtitle: "最先端のAI駆動フィードバックと分析でスピーキングスキルを変革",
                sessionText: "あなたのセッション：",
                languageLabel: "対象言語を選択：",
                languageSection: "言語選択",
                actionsSection: "クイックアクション",
                recordBtn: "スピーチ録音 (R)",
                viewBtn: "録音を表示 (L)",
                stopBtn: "録音停止 (Enter)",
                setupSection: "録音設定",
                topicLabel: "スピーチトピック",
                topicPlaceholder: "何について話しますか？",
                typeLabel: "スピーチタイプ",
                typePlaceholder: "例：面接、プレゼンテーション、討論",
                repeatLabel: "これは同じトピックの再試行です",
                startBtn: "録音開始 (T)",
                cancelBtn: "キャンセル (B)",
                recordingText: "録音中",
                recordingSubtext: "マイクに向かってはっきりと話してください。終了時は停止をクリック、破棄する場合はキャンセルをクリック。",
                cancelActiveBtn: "キャンセル (X)",
                recordingsSection: "あなたの録音",
                feedbackSection: "AIフィードバック＆分析",
                transcriptionSection: "スピーチ転写",
                playbackSection: "録音再生",
                noRecordings: "録音が見つかりません",
                noRecordingsSubtext: "最初の録音を作成して始めましょう！",
                playRecBtn: "再生",
                deleteBtn: "削除",
                recordingTooShort: "録音が短すぎます",
                recordingTooShortText: "申し訳ありません！録音が短すぎてフィードバックを生成できません。より長いスピーチで再試行してください。",
                aiAnalyzing: "AIがあなたのスピーチを分析しています"
            },
            ar: {
                title: "مُقيم الخطابات بالذكاء الاصطناعي",
                subtitle: "حول مهاراتك في التحدث مع تحليل وتغذية راجعة متطورة مدعومة بالذكاء الاصطناعي",
                sessionText: "جلستك:",
                languageLabel: "اختر لغتك المستهدفة:",
                languageSection: "اختيار اللغة",
                actionsSection: "إجراءات سريعة",
                recordBtn: "تسجيل خطاب (R)",
                viewBtn: "عرض التسجيلات (L)",
                stopBtn: "إيقاف التسجيل (Enter)",
                setupSection: "إعداد التسجيل",
                topicLabel: "موضوع الخطاب",
                topicPlaceholder: "عن ماذا ستتحدث؟",
                typeLabel: "نوع الخطاب",
                typePlaceholder: "مثال: مقابلة، عرض تقديمي، مناقشة",
                repeatLabel: "هذه محاولة ثانية لنفس الموضوع",
                startBtn: "بدء التسجيل (T)",
                cancelBtn: "إلغاء (B)",
                recordingText: "التسجيل قيد التقدم",
                recordingSubtext: "تحدث بوضوح في الميكروفون. انقر إيقاف عند الانتهاء أو إلغاء للتجاهل.",
                cancelActiveBtn: "إلغاء (X)",
                recordingsSection: "تسجيلاتك",
                feedbackSection: "تغذية راجعة وتحليل بالذكاء الاصطناعي",
                transcriptionSection: "نسخ الخطاب",
                playbackSection: "تشغيل التسجيل",
                noRecordings: "لم يتم العثور على تسجيلات",
                noRecordingsSubtext: "أنشئ تسجيلك الأول للبدء!",
                playRecBtn: "تشغيل",
                deleteBtn: "حذف",
                recordingTooShort: "التسجيل قصير جداً",
                recordingTooShortText: "عذراً! كان التسجيل قصيراً جداً لإنتاج تغذية راجعة. حاول مرة أخرى بخطاب أطول.",
                aiAnalyzing: "الذكاء الاصطناعي يحلل خطابك"
            },
            hi: {
                title: "एआई भाषण मूल्यांकनकर्ता",
                subtitle: "अत्याधुनिक एआई-संचालित फीडबैक और विश्लेषण के साथ अपने बोलने के कौशल को बदलें",
                sessionText: "आपका सत्र:",
                languageLabel: "अपनी लक्षित भाषा चुनें:",
                languageSection: "भाषा चयन",
                actionsSection: "त्वरित कार्य",
                recordBtn: "भाषण रिकॉर्ड करें (R)",
                viewBtn: "रिकॉर्डिंग देखें (L)",
                stopBtn: "रिकॉर्डिंग रोकें (Enter)",
                setupSection: "रिकॉर्डिंग सेटअप",
                topicLabel: "भाषण विषय",
                topicPlaceholder: "आप किस बारे में बात करेंगे?",
                typeLabel: "भाषण प्रकार",
                typePlaceholder: "जैसे: साक्षात्कार, प्रस्तुति, बहस",
                repeatLabel: "यह उसी विषय पर दूसरी कोशिश है",
                startBtn: "रिकॉर्डिंग शुरू करें (T)",
                cancelBtn: "रद्द करें (B)",
                recordingText: "रिकॉर्डिंग प्रगति में",
                recordingSubtext: "माइक्रोफोन में स्पष्ट रूप से बोलें। समाप्त होने पर रोकें क्लिक करें या रद्द करने के लिए रद्द करें।",
                cancelActiveBtn: "रद्द करें (X)",
                recordingsSection: "आपकी रिकॉर्डिंग",
                feedbackSection: "एआई फीडबैक और विश्लेषण",
                transcriptionSection: "भाषण प्रतिलेखन",
                playbackSection: "रिकॉर्डिंग प्लेबैक",
                noRecordings: "कोई रिकॉर्डिंग नहीं मिली",
                noRecordingsSubtext: "शुरू करने के लिए अपनी पहली रिकॉर्डिंग बनाएं!",
                playRecBtn: "चलाएं",
                deleteBtn: "हटाएं",
                recordingTooShort: "रिकॉर्डिंग बहुत छोटी",
                recordingTooShortText: "माफ़ करें! रिकॉर्डिंग फीडबैक उत्पन्न करने के लिए बहुत छोटी थी। कृपया लंबे भाषण के साथ फिर से कोशिश करें।",
                aiAnalyzing: "एआई आपके भाषण का विश्लेषण कर रहा है"
            },
            tr: {
                title: "AI Konuşma Değerlendirici",
                subtitle: "En son AI destekli geri bildirim ve analiz ile konuşma becerilerinizi dönüştürün",
                sessionText: "Oturumunuz:",
                languageLabel: "Hedef dilinizi seçin:",
                languageSection: "Dil Seçimi",
                actionsSection: "Hızlı İşlemler",
                recordBtn: "Konuşma Kaydet (R)",
                viewBtn: "Kayıtları Görüntüle (L)",
                stopBtn: "Kaydı Durdur (Enter)",
                setupSection: "Kayıt Kurulumu",
                topicLabel: "Konuşma Konusu",
                topicPlaceholder: "Ne hakkında konuşacaksınız?",
                typeLabel: "Konuşma Türü",
                typePlaceholder: "örn., mülakat, sunum, tartışma",
                repeatLabel: "Bu aynı konu üzerinde ikinci bir deneme",
                startBtn: "Kaydı Başlat (T)",
                cancelBtn: "İptal (B)",
                recordingText: "Kayıt Devam Ediyor",
                recordingSubtext: "Mikrofona açık bir şekilde konuşun. Bitirdiğinde durdur'a veya atmak için iptal'e tıklayın.",
                cancelActiveBtn: "İptal (X)",
                recordingsSection: "Kayıtlarınız",
                feedbackSection: "AI Geri Bildirim ve Analiz",
                transcriptionSection: "Konuşma Transkripsiyonu",
                playbackSection: "Kayıt Oynatma",
                noRecordings: "Kayıt bulunamadı",
                noRecordingsSubtext: "Başlamak için ilk kaydınızı oluşturun!",
                playRecBtn: "Oynat",
                deleteBtn: "Sil",
                recordingTooShort: "Kayıt Çok Kısa",
                recordingTooShortText: "Üzgünüz! Kayıt geri bildirim üretmek için çok kısaydı. Lütfen daha uzun bir konuşma ile tekrar deneyin.",
                aiAnalyzing: "AI konuşmanızı analiz ediyor"
            },
            nl: {
                title: "AI Spraak Evaluator",
                subtitle: "Transformeer je spreekvaardigheden met geavanceerde AI-aangedreven feedback en analyse",
                sessionText: "Je Sessie:",
                languageLabel: "Kies je doeltaal:",
                languageSection: "Taalselectie",
                actionsSection: "Snelle Acties",
                recordBtn: "Spraak Opnemen (R)",
                viewBtn: "Opnames Bekijken (L)",
                stopBtn: "Opname Stoppen (Enter)",
                setupSection: "Opname Instellingen",
                topicLabel: "Spraak Onderwerp",
                topicPlaceholder: "Waar ga je over spreken?",
                typeLabel: "Spraak Type",
                typePlaceholder: "bijv., interview, presentatie, debat",
                repeatLabel: "Dit is een tweede poging op hetzelfde onderwerp",
                startBtn: "Opname Starten (T)",
                cancelBtn: "Annuleren (B)",
                recordingText: "Opname Bezig",
                recordingSubtext: "Spreek duidelijk in je microfoon. Klik stop wanneer klaar of annuleren om te verwijderen.",
                cancelActiveBtn: "Annuleren (X)",
                recordingsSection: "Je Opnames",
                feedbackSection: "AI Feedback & Analyse",
                transcriptionSection: "Spraak Transcriptie",
                playbackSection: "Opname Afspelen",
                noRecordings: "Geen opnames gevonden",
                noRecordingsSubtext: "Maak je eerste opname om te beginnen!",
                playRecBtn: "Afspelen",
                deleteBtn: "Verwijderen",
                recordingTooShort: "Opname Te Kort",
                recordingTooShortText: "Sorry! De opname was te kort om feedback te genereren. Probeer opnieuw met een langere spraak.",
                aiAnalyzing: "AI analyseert je spraak"
            },
            bn: {
                title: "এআই বক্তৃতা মূল্যায়নকারী",
                subtitle: "অত্যাধুনিক এআই-চালিত ফিডব্যাক এবং বিশ্লেষণের মাধ্যমে আপনার কথা বলার দক্ষতা পরিবর্তন করুন",
                sessionText: "আপনার সেশন:",
                languageLabel: "আপনার লক্ষ্য ভাষা বেছে নিন:",
                languageSection: "ভাষা নির্বাচন",
                actionsSection: "দ্রুত কর্ম",
                recordBtn: "বক্তৃতা রেকর্ড করুন (R)",
                viewBtn: "রেকর্ডিং দেখুন (L)",
                stopBtn: "রেকর্ডিং বন্ধ করুন (Enter)",
                setupSection: "রেকর্ডিং সেটআপ",
                topicLabel: "বক্তৃতার বিষয়",
                topicPlaceholder: "আপনি কি নিয়ে কথা বলবেন?",
                typeLabel: "বক্তৃতার ধরন",
                typePlaceholder: "যেমন: সাক্ষাৎকার, উপস্থাপনা, বিতর্ক",
                repeatLabel: "এটি একই বিষয়ে দ্বিতীয় চেষ্টা",
                startBtn: "রেকর্ডিং শুরু করুন (T)",
                cancelBtn: "বাতিল (B)",
                recordingText: "রেকর্ডিং চলছে",
                recordingSubtext: "মাইক্রোফোনে স্পষ্ট করে কথা বলুন। শেষ হলে বন্ধ ক্লিক করুন বা বাতিল করতে বাতিল ক্লিক করুন।",
                cancelActiveBtn: "বাতিল (X)",
                recordingsSection: "আপনার রেকর্ডিং",
                feedbackSection: "এআই ফিডব্যাক এবং বিশ্লেষণ",
                transcriptionSection: "বক্তৃতার প্রতিলিপি",
                playbackSection: "রেকর্ডিং প্লেব্যাক",
                noRecordings: "কোন রেকর্ডিং পাওয়া যায়নি",
                noRecordingsSubtext: "শুরু করতে আপনার প্রথম রেকর্ডিং তৈরি করুন!",
                playRecBtn: "চালান",
                deleteBtn: "মুছুন",
                recordingTooShort: "রেকর্ডিং খুব ছোট",
                recordingTooShortText: "দুঃখিত! রেকর্ডিংটি ফিডব্যাক তৈরি করার জন্য খুব ছোট ছিল। অনুগ্রহ করে আরও দীর্ঘ বক্তৃতা দিয়ে আবার চেষ্টা করুন।",
                aiAnalyzing: "এআই আপনার বক্তৃতা বিশ্লেষণ করছে"
            }




        };

        document.getElementById('languageSelect').addEventListener('change', function() {
            currentLanguage = this.value;
            updateLanguage();
        });

        function updateLanguage() {
            console.log('Language changed to: ' + currentLanguage);
            
            const lang = translations[currentLanguage] || translations.en;
            
            // Update main content
            document.querySelector('.header h1').textContent = lang.title;
            document.querySelector('.header p').textContent = lang.subtitle;
            document.querySelector('#sessionInfo').innerHTML = `<i class="fas fa-user-circle"></i> ${lang.sessionText} <span id="sessionId">${document.getElementById('sessionId').textContent}</span>`;
            
            // Update language selector
            document.querySelector('label[for="languageSelect"]').textContent = lang.languageLabel;
            document.querySelector('.language-selector').previousElementSibling.querySelector('span').textContent = lang.languageSection;
            
            // Update quick actions
            document.querySelector('.controls-grid').previousElementSibling.querySelector('span').textContent = lang.actionsSection;
            document.querySelector('#recordBtn').innerHTML = `<i class="fas fa-microphone"></i> ${lang.recordBtn}`;
            document.querySelector('.btn-list').innerHTML = `<i class="fas fa-list"></i> ${lang.viewBtn}`;
            document.querySelector('#stopBtn').innerHTML = `<i class="fas fa-stop"></i> ${lang.stopBtn}`;
            
            // Update recording setup
            document.querySelector('#recordingSetup .section-title span').textContent = lang.setupSection;
            document.querySelector('label[for="topicInput"]').textContent = lang.topicLabel;
            document.querySelector('#topicInput').placeholder = lang.topicPlaceholder;
            document.querySelector('label[for="speechTypeInput"]').textContent = lang.typeLabel;
            document.querySelector('#speechTypeInput').placeholder = lang.typePlaceholder;
            document.querySelector('label[for="repeatSpeech"]').textContent = lang.repeatLabel;
            
            // Update recording setup buttons
            const setupButtons = document.querySelectorAll('#recordingSetup .controls-grid .btn');
            setupButtons[0].innerHTML = `<i class="fas fa-play"></i> ${lang.startBtn}`;
            setupButtons[1].innerHTML = `<i class="fas fa-times"></i> ${lang.cancelBtn}`;
            
            // Update recording status
            document.querySelector('.status-text').textContent = lang.recordingText;
            document.querySelector('.status-subtext').textContent = lang.recordingSubtext;
            
            // Update recording status buttons
            const statusButtons = document.querySelectorAll('#recordingStatus .btn');
            statusButtons[0].innerHTML = `<i class="fas fa-stop"></i> ${lang.stopBtn}`;
            statusButtons[1].innerHTML = `<i class="fas fa-times"></i> ${lang.cancelActiveBtn}`;
            
            // Update sections
            document.querySelector('#recordingsList .section-title span').textContent = lang.recordingsSection;
            document.querySelector('#feedbackSection .section-title span').textContent = lang.feedbackSection;
            document.querySelector('#transcriptionSection .section-title span').textContent = lang.transcriptionSection;
            document.querySelector('#audioControls .section-title span').textContent = lang.playbackSection;
            
            // Update feedback loading text
            const feedbackLoadingSpan = document.querySelector('#feedbackLoading span');
            if (feedbackLoadingSpan) {
                feedbackLoadingSpan.textContent = lang.aiAnalyzing;
            }
        }

        async function apiCall(endpoint, options = {}) {
            try {
                const headers = {
                    'Content-Type': 'application/json',
                    ...options.headers
                };
                
                if (sessionId) {
                    headers['Session-ID'] = sessionId;
                }
                
                const response = await fetch(API_BASE + endpoint, {
                    headers: headers,
                    ...options
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'HTTP ' + response.status);
                }
                
                return data;
            } catch (error) {
                console.error('API call failed for ' + endpoint + ':', error);
                showStatus('API Error: ' + error.message, 'error');
                throw error;
            }
        }

        async function checkHealth() {
            try {
                const result = await apiCall('/health');
            } catch (error) {
                showStatus('❌ Cannot connect. Please start the API server.', 'error');
            }
        }

        async function loadLanguages() {
            try {
                const result = await apiCall('/languages');
                if (result.success) {
                    const select = document.getElementById('languageSelect');
                    select.innerHTML = '';
                    
                    result.display_options.forEach(function(option) {
                        const parts = option.split(': ');
                        const code = parts[0];
                        const name = parts[1];
                        const optionElement = document.createElement('option');
                        optionElement.value = code;
                        optionElement.textContent = code + ': ' + name;
                        select.appendChild(optionElement);
                    });
                }
            } catch (error) {
                console.error('Failed to load languages:', error);
            }
        }

        function showStatus(message, type, duration) {
            if (typeof type === 'undefined') type = 'info';
            if (typeof duration === 'undefined') duration = 5000;
            
            const statusDiv = document.getElementById('statusMessage');
            statusDiv.innerHTML = '<div class="status-message status-' + type + '">' + message + '</div>';
            
            if (duration > 0) {
                setTimeout(function() {
                    statusDiv.innerHTML = '';
                }, duration);
            }
        }

        function setupKeyboardShortcuts() {
            document.addEventListener('keydown', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    return;
                }

                switch(e.key.toLowerCase()) {
                    case 'r':
                        e.preventDefault();
                        startRecording();
                        break;
                    case 'l':
                        e.preventDefault();
                        listRecordings();
                        break;
                    case 'enter':
                        if (isRecording) {
                            e.preventDefault();
                            stopRecording();
                        }
                        break;
                    case 'x':
                        if (isRecording) {
                            e.preventDefault();
                            cancelActiveRecording();
                        }
                        break;
                    case 't':
                        if (document.getElementById('recordingSetup').classList.contains('active')) {
                            e.preventDefault();
                            confirmRecording();
                        }
                        break;
                    case 'b':
                        if (document.getElementById('recordingSetup').classList.contains('active')) {
                            e.preventDefault();
                            cancelRecording();
                        }
                        break;
                    case '?':
                        e.preventDefault();
                        toggleShortcuts();
                        break;
                }
            });

            // Close modal on Escape
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    const modal = document.getElementById('shortcutsModal');
                    if (modal.classList.contains('active')) {
                        toggleShortcuts();
                    }
                }
            });
        }

        function startRecording() {
            if (isRecording) {
                showStatus('Recording already active!', 'error');
                return;
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            // Clear previous recording data
            document.getElementById('transcriptionContent').textContent = '';
            document.getElementById('feedbackText').innerHTML = '';

            document.getElementById('recordingSetup').classList.add('active');
            document.getElementById('recordingsList').classList.remove('active');
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('transcriptionSection').classList.add('hidden');
            document.getElementById('audioControls').classList.add('hidden');

            document.getElementById('topicInput').value = '';
            document.getElementById('speechTypeInput').value = '';
            document.getElementById('repeatSpeech').checked = false;
            document.getElementById('topicInput').focus();
        }

        function getSupportedMimeType() {
            const types = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/mp4',
                'audio/ogg;codecs=opus',
                'audio/wav'
            ];
            
            for (let type of types) {
                if (MediaRecorder.isTypeSupported(type)) {
                    console.log('Using MIME type:', type);
                    return type;
                }
            }
            
            console.log('Using default MIME type');
            return '';
        }

        async function convertToWAV(audioBlob) {
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const arrayBuffer = await audioBlob.arrayBuffer();
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                
                const wavArrayBuffer = audioBufferToWav(audioBuffer);
                return new Blob([wavArrayBuffer], { type: 'audio/wav' });
            } catch (error) {
                console.log('WAV conversion failed, using original:', error.message);
                return audioBlob;
            }
        }

        function cancelActiveRecording() {
            if (!isRecording || !mediaRecorder) {
                showStatus('No recording in progress', 'error');
                return;
            }

            window.shouldProcessRecording = false;
            
            try {
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                }
                
                if (mediaRecorder.stream) {
                    mediaRecorder.stream.getTracks().forEach(function(track) {
                        track.stop();
                    });
                }
            } catch (error) {
                console.log('Error stopping recorder:', error);
            }
            
            audioChunks = [];
            recordedBlob = null;
            isRecording = false;

            // Stop timer
            if (recordingTimerInterval) {
                clearInterval(recordingTimerInterval);
                recordingTimerInterval = null;
            }

            document.getElementById('recordingStatus').classList.remove('active');
            document.getElementById('recordBtn').classList.remove('recording');
            document.getElementById('stopBtn').classList.add('hidden');
            document.getElementById('recordingSetup').classList.remove('active');
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('transcriptionSection').classList.add('hidden');
            document.getElementById('audioControls').classList.add('hidden');

            showStatus('🚫 Recording cancelled - no analysis performed', 'info');
        }

        function audioBufferToWav(buffer) {
            const length = buffer.length;
            const numberOfChannels = Math.min(buffer.numberOfChannels, 2);
            const sampleRate = buffer.sampleRate;
            
            const arrayBuffer = new ArrayBuffer(44 + length * numberOfChannels * 2);
            const view = new DataView(arrayBuffer);
            
            writeString(view, 0, 'RIFF');
            view.setUint32(4, 36 + length * numberOfChannels * 2, true);
            writeString(view, 8, 'WAVE');
            writeString(view, 12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, numberOfChannels, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * numberOfChannels * 2, true);
            view.setUint16(32, numberOfChannels * 2, true);
            view.setUint16(34, 16, true);
            writeString(view, 36, 'data');
            view.setUint32(40, length * numberOfChannels * 2, true);
            
            let offset = 44;
            for (let i = 0; i < length; i++) {
                for (let channel = 0; channel < numberOfChannels; channel++) {
                    const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[i]));
                    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
                    offset += 2;
                }
            }
            
            return arrayBuffer;
        }

        function writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        async function confirmRecording() {
            const isBehavioralMode = document.getElementById('behavioralModeToggle').checked;
            let topic, speechType;

            if (isBehavioralMode) {
                const behavioralQuestion = document.getElementById('behavioralQuestionInput').value.trim();
                if (!behavioralQuestion) {
                    showStatus('Please enter a behavioral interview question', 'error');
                    return;
                }
                topic = "BEHAVIORAL:" + behavioralQuestion;
                speechType = "Behavioral Interview Response";
            } else {
                topic = document.getElementById('topicInput').value.trim();
                speechType = document.getElementById('speechTypeInput').value.trim();
                if (!topic || !speechType) {
                    showStatus('Please configure both topic and speech type for analysis', 'error');
                    return;
                }
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        sampleRate: 44100,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });

                const mimeType = getSupportedMimeType();
                const options = mimeType ? { mimeType: mimeType } : {};
                mediaRecorder = new MediaRecorder(stream, options);

                audioChunks = [];
                
                mediaRecorder.ondataavailable = function(event) {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = function() {
                    const actualMimeType = mediaRecorder.mimeType || 'audio/webm';
                    const audioBlob = new Blob(audioChunks, { type: actualMimeType });
                    recordedBlob = audioBlob;
                    
                    if (window.shouldProcessRecording !== false) {
                        console.log('Recording completed. MIME type:', actualMimeType, 'Size:', audioBlob.size);
                        processRecording();
                    }
                    
                    window.shouldProcessRecording = true;
                };

                mediaRecorder.onerror = function(event) {
                    console.error('MediaRecorder error:', event.error);
                    showStatus('Recording error: ' + event.error.message, 'error');
                };

                mediaRecorder.start(1000);
                isRecording = true;

                document.getElementById('recordingSetup').classList.remove('active');
                document.getElementById('recordingStatus').classList.add('active');
                document.getElementById('recordBtn').classList.add('recording');
                document.getElementById('stopBtn').classList.remove('hidden');

                // Start timer
                recordingStartTime = Date.now();
                document.getElementById('recordingTimer').textContent = '00:00';
                recordingTimerInterval = setInterval(updateRecordingTimer, 100);

                showStatus('🎤 Recording initiated! Speech patterns being captured...', 'info', 0);

            } catch (error) {
                console.error('Error starting recording:', error);
                showStatus('❌ Failed to initiate recording: ' + error.message, 'error');
            }
        }

        function stopRecording() {
            if (!isRecording || !mediaRecorder) {
                showStatus('No recording in progress', 'error');
                return;
            }

            window.shouldProcessRecording = true;
            
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(function(track) {
                track.stop();
            });
            isRecording = false;

            // Stop timer
            if (recordingTimerInterval) {
                clearInterval(recordingTimerInterval);
                recordingTimerInterval = null;
            }

            document.getElementById('recordingStatus').classList.remove('active');
            document.getElementById('recordBtn').classList.remove('recording');
            document.getElementById('stopBtn').classList.add('hidden');

            showStatus('⏹️ Recording completed. Initializing analysis...', 'info', 0);
        }

        function updateRecordingTimer() {
            if (!recordingStartTime) return;
            const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            const formatted = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
            document.getElementById('recordingTimer').textContent = formatted;
        }

        function cancelRecording() {
            document.getElementById('recordingSetup').classList.remove('active');
            showStatus('Recording configuration cancelled', 'info');
        }

        async function processRecording() {
            if (!recordedBlob) {
                showStatus('No recording data to process', 'error');
                return;
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            try {
                showStatus('🔄 Processing data...', 'info', 0);

                if (recordedBlob.size === 0) {
                    showStatus('❌ Recording is empty. Please try recording again.', 'error');
                    return;
                }

                if (recordedBlob.size < 1000) {
                    showStatus('❌ Recording too short for analysis. Please record for at least a few seconds.', 'error');
                    return;
                }

                const wavBlob = await convertToWAV(recordedBlob);
                
                const audioBase64 = await new Promise(function(resolve, reject) {
                    const reader = new FileReader();
                    reader.onload = function() { resolve(reader.result); };
                    reader.onerror = reject;
                    reader.readAsDataURL(wavBlob);
                });

                const isBehavioralMode = document.getElementById('behavioralModeToggle').checked;
                let topic, speechType;

                if (isBehavioralMode) {
                    const behavioralQuestion = document.getElementById('behavioralQuestionInput').value.trim();
                    topic = "BEHAVIORAL:" + behavioralQuestion;
                    speechType = "Behavioral Interview Response";
                } else {
                    topic = document.getElementById('topicInput').value.trim();
                    speechType = document.getElementById('speechTypeInput').value.trim();
                }

                const isRepeat = document.getElementById('repeatSpeech').checked;

                let audioData = audioBase64;
                if (audioData.includes(',')) {
                    audioData = audioData.split(',')[1];
                }

                const payload = {
                    topic: topic,
                    speech_type: speechType,
                    language: currentLanguage,
                    audio_data: audioData,
                    audio_format: 'audio/wav',
                    is_repeat: isRepeat
                };

                showStatus('📤 Sending to AI for analysis...', 'info', 0);

                const response = await fetch(API_BASE + '/record', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('HTTP ' + response.status + ': ' + errorText);
                }

                const result = await response.json();

                if (result.success) {
                    displayInitialResults(result.result);
                    startFeedbackStream(result.result.stream_url);
                    showStatus('✅ Analysis successfully initiated!', 'success');

                    // Silently refresh recordings list in background
                    // This ensures the archive tab is updated without bothering the user
                    updateRecordingsInBackground();
                } else {
                    showStatus('❌ Processing failed: ' + result.error, 'error');
                }

            } catch (error) {
                console.error('Processing error:', error);
                showStatus('❌ Failed to process data: ' + error.message, 'error');
            }
        }

        function displayInitialResults(result) {
            const hasTranscription = result.transcription && result.transcription.trim().length > 0;
            
            if (hasTranscription) {
                document.getElementById('transcriptionContent').textContent = result.transcription;
                document.getElementById('transcriptionSection').classList.remove('hidden');
            }

            // Show feedback section with loading state
            document.getElementById('feedbackSection').classList.add('active');
            document.getElementById('feedbackLoading').style.display = 'flex';
            document.getElementById('feedbackText').style.display = 'none';
            document.getElementById('feedbackText').innerHTML = '';

            if (recordedBlob) {
                const audioURL = URL.createObjectURL(recordedBlob);
                document.getElementById('audioPlayer').src = audioURL;
                document.getElementById('audioControls').classList.remove('hidden');
            }
        }

        function startFeedbackStream(streamUrl) {
            // Close any existing stream
            if (feedbackEventSource) {
                feedbackEventSource.close();
            }

            // Add language parameter to stream URL
            const urlWithLang = streamUrl + '?language=' + encodeURIComponent(currentLanguage);
            feedbackEventSource = new EventSource(urlWithLang);
            
            let scrollThrottle = null;

            feedbackEventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);

                    if (data.error) {
                        console.error('Stream error:', data.error);
                        showStatus('❌ Analysis failed: ' + data.error, 'error');
                        feedbackEventSource.close();
                        return;
                    }

                    if (data.type === 'chunk' && data.content) {
                        // Hide loading and show text on first chunk
                        if (document.getElementById('feedbackLoading').style.display !== 'none') {
                            document.getElementById('feedbackLoading').style.display = 'none';
                            document.getElementById('feedbackText').style.display = 'block';
                        }

                        // Efficiently append content without creating spans
                        const feedbackText = document.getElementById('feedbackText');
                        feedbackText.textContent += data.content;

                        // Throttle scroll operations to improve performance
                        if (!scrollThrottle) {
                            scrollThrottle = setTimeout(() => {
                                feedbackText.scrollTop = feedbackText.scrollHeight;
                                scrollThrottle = null;
                            }, 50);
                        }
                    }

                    if (data.type === 'complete') {
                        console.log('✓ Analysis completed, chunks received:', data.total_chunks || 'unknown');
                        // Hide loading indicator
                        document.getElementById('feedbackLoading').style.display = 'none';
                        feedbackEventSource.close();
                        feedbackEventSource = null;

                        // Clear any pending scroll
                        if (scrollThrottle) {
                            clearTimeout(scrollThrottle);
                            scrollThrottle = null;
                        }

                        // Final scroll to bottom
                        const feedbackText = document.getElementById('feedbackText');
                        feedbackText.scrollTop = feedbackText.scrollHeight;

                        // Show copy button
                        document.getElementById('copyFeedbackBtn').style.display = 'block';
                    }
                } catch (error) {
                    console.error('Error parsing stream data:', error);
                }
            };
            
            feedbackEventSource.onerror = function(event) {
                console.error('EventSource error:', event);
                feedbackEventSource.close();
                feedbackEventSource = null;

                // Only show error if no feedback was received
                const feedbackText = document.getElementById('feedbackText');
                if (feedbackText.textContent.trim() === '') {
                    document.getElementById('feedbackLoading').style.display = 'none';
                    showStatus('❌ Analysis failed: Connection error', 'error');
                }
            };
        }

        async function updateRecordingsInBackground() {
            try {
                const result = await apiCall('/recordings');
                if (result.success) {
                    recordings = result.recordings || [];
                    // Update the display if the recordings tab is currently visible
                    if (document.getElementById('recordingsList').classList.contains('active')) {
                        displayRecordingsList();
                    }
                }
            } catch (error) {
                // Silently fail - this is a background update
                console.log('Background recordings update failed');
            }
        }

        async function listRecordings() {
            try {
                showStatus('📋 Loading recordings...', 'info');
                const result = await apiCall('/recordings');

                if (result.success) {
                    recordings = result.recordings || [];
                    displayRecordingsList();

                    // Always reset to list view (hide details if open)
                    document.getElementById('recordingDetails').classList.add('hidden');
                    document.getElementById('recordingsContainer').style.display = 'grid';

                    // Show recordings list and hide other sections
                    document.getElementById('recordingsList').classList.add('active');
                    document.getElementById('recordingSetup').classList.remove('active');
                    document.getElementById('feedbackSection').classList.remove('active');
                    document.getElementById('transcriptionSection').classList.add('hidden');
                    document.getElementById('audioControls').classList.add('hidden');

                    showStatus(recordings.length === 0 ? '📁 Recording list is empty' : 'Found ' + recordings.length + ' recordings', 'info');
                } else {
                    recordings = [];
                    displayRecordingsList();

                    // Always reset to list view
                    document.getElementById('recordingDetails').classList.add('hidden');
                    document.getElementById('recordingsContainer').style.display = 'grid';

                    document.getElementById('recordingsList').classList.add('active');
                    document.getElementById('feedbackSection').classList.remove('active');
                    document.getElementById('transcriptionSection').classList.add('hidden');
                    document.getElementById('audioControls').classList.add('hidden');

                    showStatus('📁 Recording list not yet initialized', 'info');
                }
            } catch (error) {
                recordings = [];
                displayRecordingsList();

                // Always reset to list view
                document.getElementById('recordingDetails').classList.add('hidden');
                document.getElementById('recordingsContainer').style.display = 'grid';

                document.getElementById('recordingsList').classList.add('active');
                document.getElementById('recordingSetup').classList.remove('active');
                document.getElementById('feedbackSection').classList.remove('active');
                document.getElementById('transcriptionSection').classList.add('hidden');
                document.getElementById('audioControls').classList.add('hidden');

                showStatus('📁 Recording list not yet initialized', 'info');
            }
        }

        function displayRecordingsList() {
            const container = document.getElementById('recordingsContainer');
            const lang = translations[currentLanguage] || translations.en;

            if (recordings.length === 0) {
                container.innerHTML = `<div class="recording-item" style="background: linear-gradient(135deg, rgba(25, 25, 50, 0.9), rgba(60, 45, 120, 0.6));"><div class="recording-info"><h4 style="color: var(--text-primary);">📁 ${lang.noRecordings}</h4><div class="recording-meta" style="color: var(--text-secondary);">${lang.noRecordingsSubtext}</div></div></div>`;
                return;
            }

            const recordingItems = recordings.map(function(recording, index) {
                const safeFilename = recording.filename.replace(/'/g, "\\\\'");

                // Create a clean title from the topic instead of showing the filename
                let displayTitle = recording.topic || 'Untitled Recording';

                // Truncate title if too long
                const maxLength = 60;
                if (displayTitle.length > maxLength) {
                    displayTitle = displayTitle.substring(0, maxLength) + '...';
                }

                // Escape HTML characters for display
                displayTitle = displayTitle.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

                return `<div class="recording-item" onclick="viewRecordingDetails(${index})" style="cursor: pointer;"><div class="recording-info"><h4><i class="fas fa-file-audio"></i> ${displayTitle}</h4><div class="recording-meta">Size: ${formatFileSize(recording.size)} | Created: ${formatDate(recording.created)}</div></div><div class="recording-actions" onclick="event.stopPropagation();"><button class="btn btn-stop btn-small" onclick="deleteRecording('${safeFilename}')" style="background: var(--danger-gradient);"><i class="fas fa-trash"></i> ${lang.deleteBtn}</button></div></div>`;
            });

            container.innerHTML = recordingItems.join('');
        }

        async function viewRecordingDetails(index) {
            const recording = recordings[index];
            if (!recording) return;

            // Update title
            let displayTitle = recording.topic || 'Untitled Recording';
            document.getElementById('detailsTitle').textContent = displayTitle;

            // Show transcription
            document.getElementById('detailsTranscriptionContent').textContent = recording.transcription || 'No transcription available';

            // Show feedback
            document.getElementById('detailsFeedbackContent').textContent = recording.feedback || 'No feedback available';

            // Load and show audio
            try {
                const response = await fetch(API_BASE + '/recordings/' + recording.filename, {
                    headers: {
                        'Session-ID': sessionId
                    }
                });
                if (response.ok) {
                    const audioBlob = await response.blob();
                    const audioURL = URL.createObjectURL(audioBlob);
                    document.getElementById('detailsAudioPlayer').src = audioURL;
                }
            } catch (error) {
                console.error('Failed to load audio:', error);
            }

            // Hide the old sections used for new recordings
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('transcriptionSection').classList.add('hidden');
            document.getElementById('audioControls').classList.add('hidden');

            // Show details section and hide main list
            document.getElementById('recordingsContainer').style.display = 'none';
            document.getElementById('recordingDetails').classList.remove('hidden');
        }

        function closeRecordingDetails() {
            // Hide details and show main list
            document.getElementById('recordingDetails').classList.add('hidden');
            document.getElementById('recordingsContainer').style.display = 'grid';

            // Stop audio playback
            const audioPlayer = document.getElementById('detailsAudioPlayer');
            audioPlayer.pause();
            audioPlayer.src = '';
        }

        async function playRecording(filename) {
            try {
                showStatus('▶️ Loading recording: ' + filename + '...', 'info');
                const response = await fetch(API_BASE + '/recordings/' + filename, {
                    headers: {
                        'Session-ID': sessionId
                    }
                });
                if (!response.ok) {
                    throw new Error('Failed to load recording: ' + response.status);
                }
                const audioBlob = await response.blob();
                const audioURL = URL.createObjectURL(audioBlob);
                document.getElementById('audioPlayer').src = audioURL;
                document.getElementById('audioControls').classList.remove('hidden');
                document.getElementById('audioPlayer').play();
                showStatus('🔊 Playing recording: ' + filename, 'success');
            } catch (error) {
                showStatus('❌ Failed to play recording', 'error');
            }
        }

        async function deleteRecording(filename) {
            if (!confirm('Are you sure you want to delete "' + filename + '" from the recording list?')) {
                return;
            }
            try {
                const result = await apiCall('/recordings/' + filename, { method: 'DELETE' });
                if (result.success) {
                    showStatus('✅ Deleted from recording list: ' + filename, 'success');
                    listRecordings();
                } else {
                    showStatus('❌ Failed to delete from recording list', 'error');
                }
            } catch (error) {
                console.error('Error deleting recording:', error);
            }
        }


        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }

        function formatDate(timestamp) {
            return new Date(timestamp * 1000).toLocaleString();
        }

        // Tab Switching

        // Switch between Home and About pages
        function switchPage(pageName) {
            // Hide all pages
            document.querySelectorAll('.page-content').forEach(page => {
                page.classList.remove('active');
            });
            document.querySelectorAll('.top-nav-link').forEach(link => {
                link.classList.remove('active');
            });

            // Show selected page
            document.getElementById(pageName + 'Page').classList.add('active');
            event.target.closest('.top-nav-link').classList.add('active');
        }
        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });

            // Show selected tab
            document.getElementById(tabName + 'Tab').classList.add('active');
            event.target.closest('.nav-tab').classList.add('active');
        }

        // Behavioral Interview Mode Toggle
        function toggleBehavioralMode() {
            const isEnabled = document.getElementById('behavioralModeToggle').checked;
            const indicator = document.getElementById('behavioralIndicator');
            const standardFields = document.getElementById('standardFields');
            const behavioralField = document.getElementById('behavioralField');
            const modeDescription = document.getElementById('modeDescription');
            const repeatCheckbox = document.querySelector('.checkbox-wrapper');

            if (isEnabled) {
                indicator.style.display = 'flex';
                standardFields.style.display = 'none';
                behavioralField.style.display = 'block';
                repeatCheckbox.style.display = 'none';
                modeDescription.innerHTML = '<p>Behavioral interview prep mode - Practice answering behavioral questions using the STAR method (Situation, Task, Action, Result) for structured, compelling responses</p>';
            } else {
                indicator.style.display = 'none';
                standardFields.style.display = 'grid';
                behavioralField.style.display = 'none';
                repeatCheckbox.style.display = 'block';
                modeDescription.innerHTML = '<p>General speaking practice mode - Focus on articulating ideas smoothly and improving overall communication skills</p>';
            }
        }

        // Behavioral Questions
        const behavioralQuestions = {
            challenge: "Tell me about a time when you faced a significant challenge at work or school. How did you handle it?",
            conflict: "Describe a situation where you had to resolve a conflict with a coworker or team member. What was the outcome?",
            leadership: "Give me an example of when you demonstrated leadership, even if you weren't in a formal leadership role.",
            failure: "Tell me about a time you failed at something. What did you learn from that experience?",
            teamwork: "Describe your experience working in a difficult team dynamic. How did you navigate it?",
            initiative: "Tell me about a time when you went above and beyond your job responsibilities. What motivated you?",
            pressure: "Describe a situation where you had to work under tight deadlines or intense pressure. How did you manage?",
            impact: "Tell me about a project or initiative where you made a significant impact. What was your role?"
        };

        function loadBehavioralQuestion(questionKey) {
            const question = behavioralQuestions[questionKey];
            if (!question) return;

            // Switch to record tab
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById('recordTab').classList.add('active');
            document.querySelectorAll('.nav-tab')[0].classList.add('active');

            // Enable behavioral mode
            document.getElementById('behavioralModeToggle').checked = true;
            toggleBehavioralMode();

            // Make sure recording setup is visible
            document.getElementById('recordingSetup').classList.add('active');
            document.getElementById('recordingsList').classList.remove('active');
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('recordingStatus').classList.remove('active');

            // Fill in the question
            document.getElementById('behavioralQuestionInput').value = question;

            // Show confirmation
            showStatus('✓ Behavioral question loaded: ' + questionKey, 'success');

            // Scroll to show form
            requestAnimationFrame(() => {
                const behavioralField = document.getElementById('behavioralField');
                const rect = behavioralField.getBoundingClientRect();
                const offset = window.pageYOffset + rect.top - 120;
                window.scrollTo({ top: offset, behavior: 'auto' });
            });
        }

        // Practice Scenarios
        const scenarios = {
            elevator: {
                topic: "30-Second Elevator Pitch",
                type: "Professional Introduction"
            },
            persuasive: {
                topic: "Convincing Argument on My Position",
                type: "Persuasive Speech"
            },
            toast: {
                topic: "Wedding Toast for the Couple",
                type: "Special Occasion Speech"
            },
            intro: {
                topic: "Introduction to Who I Am",
                type: "Professional, Formal Introduction"
            },
            demo: {
                topic: "Product or Idea Presentation",
                type: "Demonstration Speech"
            },
            story: {
                topic: "Personal Story with a Lesson",
                type: "Storytelling"
            },
            interview: {
                topic: "Tell Me About Yourself - Job Interview",
                type: "Professional Interview Response"
            },
            debate: {
                topic: "Counterargument on a Controversial Topic",
                type: "Debate Speech"
            }
        };

        function loadScenario(scenarioKey) {
            const scenario = scenarios[scenarioKey];
            if (!scenario) return;

            // Directly switch tabs without click event
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            document.getElementById('recordTab').classList.add('active');
            document.querySelectorAll('.nav-tab')[0].classList.add('active');

            // Make sure recording setup is visible
            document.getElementById('recordingSetup').classList.add('active');
            document.getElementById('recordingsList').classList.remove('active');
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('recordingStatus').classList.remove('active');

            // Fill in the form
            document.getElementById('topicInput').value = scenario.topic;
            document.getElementById('speechTypeInput').value = scenario.type;

            // Show confirmation
            showStatus('✓ Scenario loaded: ' + scenario.topic, 'success');

            // Scroll to show form with a bit less aggressive positioning
            requestAnimationFrame(() => {
                const topicInput = document.getElementById('topicInput');
                const rect = topicInput.getBoundingClientRect();
                const offset = window.pageYOffset + rect.top - 120; // 120px from top instead of center
                window.scrollTo({ top: offset, behavior: 'auto' });
            });
        }

        // Toggle Keyboard Shortcuts Modal
        function toggleShortcuts() {
            const modal = document.getElementById('shortcutsModal');
            modal.classList.toggle('active');
        }

        // Copy Feedback
        function copyFeedback() {
            const feedbackText = document.getElementById('feedbackText').innerText;

            navigator.clipboard.writeText(feedbackText).then(() => {
                const btn = document.getElementById('copyFeedbackBtn');
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                btn.style.background = 'rgba(34, 197, 94, 0.2)';
                btn.style.borderColor = 'rgba(34, 197, 94, 0.3)';

                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.style.background = '';
                    btn.style.borderColor = '';
                }, 2000);
            }).catch(err => {
                showStatus('Failed to copy feedback', 'error');
            });
        }
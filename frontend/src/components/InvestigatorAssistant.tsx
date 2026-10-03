import React, { useState } from 'react';
import { apiClient } from '../services/api/client';
import type { Case } from '../types/case';
import type {
  EvidenceCitation,
  RAGQueryResponse,
} from '../types/rag';

interface InvestigatorAssistantProps {
  caseId: string;
  caseData: Case | null;
}

export const InvestigatorAssistant: React.FC<InvestigatorAssistantProps> = ({
  caseId,
  caseData,
}) => {
  const [queryText, setQueryText] = useState('');
  const [conversationId, setConversationId] = useState<string>(() => `session-${Date.now()}`);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Turn history
  const [turns, setTurns] = useState<
    Array<{
      id: string;
      query: string;
      response?: RAGQueryResponse;
      error?: string;
    }>
  >([]);

  // Selected citation modal state
  const [selectedCitation, setSelectedCitation] = useState<EvidenceCitation | null>(null);

  const sampleQueries = [
    'What messages mention meeting or warehouse?',
    'What communication occurred between participants?',
    'What events occurred between 8:00 PM and 10:00 PM?',
    'What WhatsApp messages were recorded on the device?',
    'Are there conflicting records logged for any event?',
  ];

  const handleSendQuery = async (queryToSend?: string) => {
    const q = (queryToSend || queryText).trim();
    if (!q || isLoading) return;

    const turnId = `turn-${Date.now()}`;
    setTurns((prev) => [...prev, { id: turnId, query: q }]);
    setQueryText('');
    setIsLoading(true);
    setErrorMessage(null);

    try {
      const res: RAGQueryResponse = await apiClient.executeRAGQuery(caseId, {
        query: q,
        conversation_id: conversationId,
        max_context_records: 15,
        include_citations: true,
      });

      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, response: res } : t))
      );
    } catch (err: any) {
      const msg = err.message || 'Failed to execute RAG query';
      setErrorMessage(msg);
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, error: msg } : t))
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearSession = async () => {
    try {
      await apiClient.clearRAGConversation(caseId, conversationId);
    } catch {
      // ignore
    }
    setTurns([]);
    setConversationId(`session-${Date.now()}`);
    setErrorMessage(null);
  };

  return (
    <div style={styles.container}>
      {/* Header Banner */}
      <div style={styles.header}>
        <div style={styles.headerTitleGroup}>
          <div style={styles.headerIcon}>🤖</div>
          <div>
            <h1 style={styles.headerTitle}>Evidence-Grounded Investigator Assistant</h1>
            <div style={styles.headerSubtitle}>
              Phase 12 RAG & Forensic Retrieval Assistant • Case: {caseData?.case_number || caseId}
            </div>
          </div>
        </div>

        <div style={styles.headerMetaGroup}>
          <div style={styles.modelBadge}>
            <span style={styles.statusDot} />
            LOCAL / DETERMINISTIC AIR-GAPPED RAG (ZERO-HALLUCINATION)
          </div>
          <button onClick={handleClearSession} style={styles.clearBtn} title="Reset Conversation Session">
            ↺ NEW INQUIRY SESSION
          </button>
        </div>
      </div>

      {/* Main Workspace Area */}
      <div style={styles.contentGrid}>
        {/* Left / Main Chat Feed */}
        <div style={styles.chatArea}>
          {errorMessage && (
            <div style={{ ...styles.errorBox, marginBottom: '16px' }}>
              <div style={styles.errorHeading}>⚠ System Notice</div>
              <div>{errorMessage}</div>
            </div>
          )}
          {turns.length === 0 ? (
            <div style={styles.welcomeBox}>
              <div style={styles.welcomeIcon}>🛡️</div>
              <h2 style={styles.welcomeTitle}>Forensic Investigator AI Assistant</h2>
              <p style={styles.welcomeDesc}>
                Ask natural-language questions regarding digital evidence in this case.
                All generated statements are strictly grounded in retrieved UFDR records and cite verified evidence tags.
              </p>

              <div style={styles.complianceNotice}>
                <div style={styles.noticeHeading}>FORENSIC SAFETY & GROUNDING STANDARD</div>
                <ul style={styles.noticeList}>
                  <li>Answers are derived strictly from retrieved canonical evidence records for this case.</li>
                  <li>Cross-case isolation is enforced; evidence from other cases cannot be retrieved.</li>
                  <li>Every factual claim cites its origin record [EVIDENCE-xxx].</li>
                  <li>The assistant does NOT determine guilt, criminal intent, or make legal declarations.</li>
                </ul>
              </div>

              <div style={styles.quickQuerySection}>
                <div style={styles.quickLabel}>EXAMPLE INVESTIGATION INQUIRIES:</div>
                <div style={styles.quickList}>
                  {sampleQueries.map((sq, i) => (
                    <button
                      key={i}
                      onClick={() => handleSendQuery(sq)}
                      style={styles.quickBtn}
                    >
                      💬 {sq}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div style={styles.turnsList}>
              {turns.map((turn) => (
                <div key={turn.id} style={styles.turnCard}>
                  {/* Investigator Query Bubble */}
                  <div style={styles.userBubble}>
                    <div style={styles.userLabelRow}>
                      <span style={styles.userAvatar}>👤</span>
                      <span style={styles.userName}>INVESTIGATOR INQUIRY</span>
                    </div>
                    <div style={styles.userText}>{turn.query}</div>
                  </div>

                  {/* Assistant Answer Card */}
                  {turn.response ? (
                    <div style={styles.assistantCard}>
                      <div style={styles.assistantHeader}>
                        <div style={styles.assistantLabelGroup}>
                          <span style={styles.assistantAvatar}>🤖</span>
                          <span style={styles.assistantName}>FORENSIC ASSISTANT</span>
                          <span style={styles.latencyBadge}>
                            ⏱ {turn.response.latency_ms} ms
                          </span>
                          {turn.response.validation_report.is_valid ? (
                            <span style={styles.verifiedBadge}>✓ CITATIONS VERIFIED</span>
                          ) : (
                            <span style={styles.warningBadge}>⚠ VALIDATION WARNING</span>
                          )}
                        </div>

                        <div style={styles.providerTag}>
                          Provider: {turn.response.reproducibility.llm_provider} ({turn.response.reproducibility.llm_model})
                        </div>
                      </div>

                      {/* NLP Intent Plan Preview */}
                      {turn.response.investigation_plan && (
                        <div style={styles.planBanner}>
                          <span style={styles.planLabel}>NLP INTERPRETATION:</span>
                          <span style={styles.planIntent}>
                            Intent: {turn.response.investigation_plan.intent || 'GENERAL_SEARCH'}
                          </span>
                          <span style={styles.planMode}>
                            Mode: {turn.response.investigation_plan.recommended_mode || 'HYBRID'}
                          </span>
                          {turn.response.investigation_plan.entities?.length > 0 && (
                            <span style={styles.planEntities}>
                              Entities: {turn.response.investigation_plan.entities.map((e: any) => e.text || e).join(', ')}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Answer Body */}
                      <div style={styles.answerSection}>
                        <div style={styles.sectionHeaderTitle}>ANSWER & FINDINGS</div>
                        <div style={styles.answerText}>
                          {turn.response.answer.split('\n').map((line, idx) => {
                            if (!line.trim()) return <div key={idx} style={{ height: '8px' }} />;
                            return (
                              <p key={idx} style={styles.answerParagraph}>
                                {renderAnswerWithClickableCitations(
                                  line,
                                  turn.response?.evidence_references || [],
                                  setSelectedCitation
                                )}
                              </p>
                            );
                          })}
                        </div>
                      </div>

                      {/* Conflicting Evidence Alert */}
                      {turn.response.conflicting_evidence && turn.response.conflicting_evidence.length > 0 && (
                        <div style={styles.conflictBox}>
                          <div style={styles.conflictHeading}>
                            ⚠ CONFLICTING EVIDENCE IDENTIFIED IN CASE RECORDS
                          </div>
                          {turn.response.conflicting_evidence.map((c, ci) => (
                            <div key={ci} style={styles.conflictItem}>
                              <div style={styles.conflictField}>Field: {c.field_name}</div>
                              <div style={styles.conflictDesc}>{c.conflict_description}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Evidence Sources / Citations List */}
                      {turn.response.evidence_references && turn.response.evidence_references.length > 0 && (
                        <div style={styles.citationsSection}>
                          <div style={styles.sectionHeaderTitle}>
                            SUPPORTING EVIDENCE CITATIONS ({turn.response.evidence_references.length})
                          </div>
                          <div style={styles.citationsGrid}>
                            {turn.response.evidence_references.map((cit, cidx) => (
                              <div
                                key={cidx}
                                style={styles.citationCard}
                                onClick={() => setSelectedCitation(cit)}
                              >
                                <div style={styles.citationCardHeader}>
                                  <span style={styles.citationTagBadge}>{cit.citation_tag}</span>
                                  <span style={styles.citType}>{cit.artifact_type.toUpperCase()}</span>
                                  {cit.source_application && (
                                    <span style={styles.citApp}>{cit.source_application}</span>
                                  )}
                                </div>
                                {cit.timestamp && (
                                  <div style={styles.citTime}>Timestamp: {cit.timestamp}</div>
                                )}
                                {(cit.sender || cit.receiver) && (
                                  <div style={styles.citParties}>
                                    {cit.sender && `From: ${cit.sender} `}
                                    {cit.receiver && `To: ${cit.receiver}`}
                                  </div>
                                )}
                                <div style={styles.citSnippet}>"{cit.content_snippet}"</div>
                                <div style={styles.citAction}>[Click to Inspect Provenance]</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Uncertainty & Limitations Panel */}
                      {(turn.response.uncertainty || turn.response.limitations) && (
                        <div style={styles.caveatsGrid}>
                          {turn.response.uncertainty && (
                            <div style={styles.caveatCard}>
                              <div style={styles.caveatLabel}>UNCERTAINTY & OBSERVATIONS</div>
                              <div style={styles.caveatText}>{turn.response.uncertainty}</div>
                            </div>
                          )}
                          {turn.response.limitations && (
                            <div style={styles.caveatCard}>
                              <div style={styles.caveatLabel}>INVESTIGATION LIMITATIONS</div>
                              <div style={styles.caveatText}>{turn.response.limitations}</div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Audit & Reproducibility Footer */}
                      <div style={styles.reproducibilityBar}>
                        <span>Query ID: {turn.response.query_id.substring(0, 8)}...</span>
                        <span>Prompt v{turn.response.reproducibility.prompt_version}</span>
                        <span>Temp: {turn.response.reproducibility.temperature}</span>
                        <span>Retrieved Top-K: {turn.response.reproducibility.retrieval_top_k}</span>
                        {turn.response.audit_log_id && (
                          <span>Audit ID: {turn.response.audit_log_id.substring(0, 8)}...</span>
                        )}
                      </div>
                    </div>
                  ) : turn.error ? (
                    <div style={styles.errorBox}>
                      <div style={styles.errorHeading}>⚠ RAG Inquiry Error</div>
                      <div>{turn.error}</div>
                    </div>
                  ) : (
                    <div style={styles.loadingBox}>
                      <span style={styles.loadingSpin}>⚙</span>
                      <span>Retrieving evidence & synthesizing grounded answer...</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={styles.inputBar}>
          <div style={styles.inputWrapper}>
            <input
              type="text"
              value={queryText}
              disabled={isLoading}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendQuery();
              }}
              placeholder="Ask an evidence-grounded question about this case (e.g. 'What messages mention warehouse?')..."
              style={styles.queryInput}
            />
            <button
              onClick={() => handleSendQuery()}
              disabled={isLoading || !queryText.trim()}
              style={{
                ...styles.sendBtn,
                opacity: isLoading || !queryText.trim() ? 0.6 : 1,
              }}
            >
              {isLoading ? 'ANALYZING...' : 'ASK ASSISTANT →'}
            </button>
          </div>
        </div>
      </div>

      {/* Evidence Citation Inspection Modal */}
      {selectedCitation && (
        <div style={styles.modalOverlay} onClick={() => setSelectedCitation(null)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div style={styles.modalTitle}>
                <span style={styles.citationTagBadge}>{selectedCitation.citation_tag}</span>
                <span>Forensic Evidence Provenance Inspector</span>
              </div>
              <button onClick={() => setSelectedCitation(null)} style={styles.closeBtn}>
                ✕
              </button>
            </div>

            <div style={styles.modalBody}>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Artifact Type:</span>
                <span style={styles.inspVal}>{selectedCitation.artifact_type}</span>
              </div>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Application:</span>
                <span style={styles.inspVal}>{selectedCitation.source_application || 'N/A'}</span>
              </div>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Timestamp:</span>
                <span style={styles.inspVal}>{selectedCitation.timestamp || 'N/A'}</span>
              </div>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Sender / From:</span>
                <span style={styles.inspVal}>{selectedCitation.sender || 'N/A'}</span>
              </div>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Receiver / To:</span>
                <span style={styles.inspVal}>{selectedCitation.receiver || 'N/A'}</span>
              </div>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Canonical ID:</span>
                <span style={styles.inspValMono}>{selectedCitation.canonical_id}</span>
              </div>
              <div style={styles.inspectorRow}>
                <span style={styles.inspLabel}>Evidence ID:</span>
                <span style={styles.inspValMono}>{selectedCitation.evidence_id}</span>
              </div>

              <div style={styles.inspectorContentBox}>
                <div style={styles.inspBoxLabel}>RECORD CONTENT:</div>
                <div style={styles.inspBoxContent}>{selectedCitation.content_snippet}</div>
              </div>

              <div style={styles.inspectorReasonBox}>
                <div style={styles.inspBoxLabel}>GROUNDING RATIONALE:</div>
                <div style={styles.inspReasonText}>{selectedCitation.reason}</div>
              </div>
            </div>

            <div style={styles.modalFooter}>
              <button onClick={() => setSelectedCitation(null)} style={styles.doneBtn}>
                CLOSE INSPECTOR
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function renderAnswerWithClickableCitations(
  line: string,
  citations: EvidenceCitation[],
  onSelectCitation: (cit: EvidenceCitation) => void
) {
  const parts = line.split(/(\[EVIDENCE-\d{3,4}\])/g);
  return parts.map((part, i) => {
    const match = part.match(/\[(EVIDENCE-\d{3,4})\]/);
    if (match) {
      const tag = match[1];
      const foundCit = citations.find((c) => c.citation_tag === tag);
      return (
        <span
          key={i}
          onClick={() => foundCit && onSelectCitation(foundCit)}
          style={styles.inlineCitationBadge}
          title={foundCit ? `Inspect ${tag} (${foundCit.artifact_type})` : tag}
        >
          {part}
        </span>
      );
    }
    return part;
  });
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    backgroundColor: 'var(--bg-primary, #0a0f1d)',
    color: 'var(--text-primary, #f8fafc)',
    fontFamily: 'var(--font-sans, system-ui, sans-serif)',
  },
  header: {
    padding: '16px 24px',
    backgroundColor: 'var(--bg-surface, #0f172a)',
    borderBottom: '1px solid var(--border-subtle, #1e293b)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '12px',
  },
  headerTitleGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  headerIcon: {
    fontSize: '28px',
  },
  headerTitle: {
    fontSize: '18px',
    fontWeight: 700,
    color: '#f8fafc',
    margin: 0,
  },
  headerSubtitle: {
    fontSize: '12px',
    color: 'var(--text-muted, #94a3b8)',
    marginTop: '2px',
  },
  headerMetaGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  modelBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    backgroundColor: '#022c22',
    border: '1px solid #059669',
    color: '#34d399',
    fontSize: '11px',
    fontWeight: 700,
    padding: '6px 12px',
    borderRadius: '4px',
    letterSpacing: '0.5px',
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#10b981',
  },
  clearBtn: {
    backgroundColor: 'transparent',
    border: '1px solid var(--border-subtle, #334155)',
    color: '#94a3b8',
    fontSize: '11px',
    fontWeight: 700,
    padding: '6px 12px',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  contentGrid: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  chatArea: {
    flex: 1,
    overflowY: 'auto',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
  },
  welcomeBox: {
    maxWidth: '800px',
    margin: '40px auto',
    backgroundColor: 'var(--bg-surface, #0f172a)',
    border: '1px solid var(--border-subtle, #1e293b)',
    borderRadius: '8px',
    padding: '32px',
    textAlign: 'center',
  },
  welcomeIcon: {
    fontSize: '40px',
    marginBottom: '12px',
  },
  welcomeTitle: {
    fontSize: '20px',
    fontWeight: 700,
    color: '#f8fafc',
    marginBottom: '8px',
  },
  welcomeDesc: {
    fontSize: '14px',
    color: '#94a3b8',
    lineHeight: 1.6,
    marginBottom: '24px',
  },
  complianceNotice: {
    textAlign: 'left',
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '16px',
    marginBottom: '24px',
  },
  noticeHeading: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#38bdf8',
    letterSpacing: '0.5px',
    marginBottom: '8px',
  },
  noticeList: {
    fontSize: '12px',
    color: '#cbd5e1',
    lineHeight: 1.6,
    margin: 0,
    paddingLeft: '18px',
  },
  quickQuerySection: {
    textAlign: 'left',
  },
  quickLabel: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#64748b',
    letterSpacing: '0.5px',
    marginBottom: '10px',
  },
  quickList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  quickBtn: {
    textAlign: 'left',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    color: '#e2e8f0',
    padding: '10px 14px',
    borderRadius: '6px',
    fontSize: '13px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  turnsList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    maxWidth: '900px',
    margin: '0 auto',
    width: '100%',
  },
  turnCard: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '14px 18px',
    maxWidth: '85%',
  },
  userLabelRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '10px',
    fontWeight: 700,
    color: '#38bdf8',
    marginBottom: '4px',
  },
  userAvatar: {
    fontSize: '12px',
  },
  userName: {
    letterSpacing: '0.5px',
  },
  userText: {
    fontSize: '14px',
    color: '#f8fafc',
    lineHeight: 1.5,
  },
  assistantCard: {
    backgroundColor: 'var(--bg-surface, #0f172a)',
    border: '1px solid var(--border-subtle, #1e293b)',
    borderRadius: '8px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  assistantHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #1e293b',
    paddingBottom: '12px',
    flexWrap: 'wrap',
    gap: '8px',
  },
  assistantLabelGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  assistantAvatar: {
    fontSize: '16px',
  },
  assistantName: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#06b6d4',
    letterSpacing: '0.5px',
  },
  latencyBadge: {
    fontSize: '11px',
    fontFamily: 'monospace',
    color: '#94a3b8',
    backgroundColor: '#090d16',
    padding: '2px 6px',
    borderRadius: '3px',
  },
  verifiedBadge: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#34d399',
    backgroundColor: '#064e3b',
    padding: '3px 8px',
    borderRadius: '3px',
    border: '1px solid #059669',
  },
  warningBadge: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#fbbf24',
    backgroundColor: '#78350f',
    padding: '3px 8px',
    borderRadius: '3px',
  },
  providerTag: {
    fontSize: '11px',
    color: '#64748b',
    fontFamily: 'monospace',
  },
  planBanner: {
    backgroundColor: '#0b1329',
    border: '1px solid #1e293b',
    borderRadius: '4px',
    padding: '8px 12px',
    fontSize: '11px',
    color: '#94a3b8',
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px',
  },
  planLabel: {
    fontWeight: 700,
    color: '#38bdf8',
  },
  planIntent: {
    color: '#f8fafc',
  },
  planMode: {
    color: '#f8fafc',
  },
  planEntities: {
    color: '#f8fafc',
  },
  answerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  sectionHeaderTitle: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#64748b',
    letterSpacing: '0.5px',
  },
  answerText: {
    fontSize: '14px',
    color: '#e2e8f0',
    lineHeight: 1.6,
  },
  answerParagraph: {
    margin: '4px 0',
  },
  inlineCitationBadge: {
    display: 'inline-block',
    backgroundColor: '#083344',
    border: '1px solid #0891b2',
    color: '#38bdf8',
    padding: '1px 6px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 700,
    fontFamily: 'monospace',
    cursor: 'pointer',
    margin: '0 2px',
    transition: 'all 0.15s ease',
  },
  conflictBox: {
    backgroundColor: '#451a03',
    border: '1px solid #d97706',
    borderRadius: '6px',
    padding: '12px 16px',
  },
  conflictHeading: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#fbbf24',
    marginBottom: '6px',
  },
  conflictItem: {
    fontSize: '12px',
    color: '#fef3c7',
  },
  conflictField: {
    fontWeight: 600,
  },
  conflictDesc: {
    marginTop: '2px',
  },
  citationsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  citationsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '10px',
  },
  citationCard: {
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    cursor: 'pointer',
    transition: 'border-color 0.15s ease',
  },
  citationCardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    marginBottom: '4px',
  },
  citationTagBadge: {
    backgroundColor: '#083344',
    color: '#38bdf8',
    border: '1px solid #0891b2',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'monospace',
    padding: '2px 6px',
    borderRadius: '3px',
  },
  citType: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#94a3b8',
  },
  citApp: {
    fontSize: '10px',
    color: '#10b981',
    backgroundColor: '#022c22',
    padding: '2px 5px',
    borderRadius: '3px',
  },
  citTime: {
    fontSize: '11px',
    color: '#94a3b8',
    fontFamily: 'monospace',
  },
  citParties: {
    fontSize: '11px',
    color: '#cbd5e1',
  },
  citSnippet: {
    fontSize: '12px',
    color: '#e2e8f0',
    fontStyle: 'italic',
    lineHeight: 1.4,
    marginTop: '4px',
  },
  citAction: {
    fontSize: '10px',
    fontWeight: 600,
    color: '#38bdf8',
    marginTop: '6px',
    textAlign: 'right',
  },
  caveatsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  caveatCard: {
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '4px',
    padding: '10px 12px',
  },
  caveatLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#94a3b8',
    marginBottom: '4px',
    letterSpacing: '0.5px',
  },
  caveatText: {
    fontSize: '12px',
    color: '#cbd5e1',
    lineHeight: 1.4,
  },
  reproducibilityBar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px',
    fontSize: '10px',
    color: '#64748b',
    fontFamily: 'monospace',
    borderTop: '1px solid #1e293b',
    paddingTop: '10px',
  },
  errorBox: {
    backgroundColor: '#450a0a',
    border: '1px solid #dc2626',
    borderRadius: '6px',
    padding: '14px',
    color: '#fca5a5',
    fontSize: '13px',
  },
  errorHeading: {
    fontWeight: 700,
    marginBottom: '4px',
  },
  loadingBox: {
    backgroundColor: '#0f172a',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    color: '#38bdf8',
    fontSize: '13px',
  },
  loadingSpin: {
    fontSize: '18px',
    animation: 'spin 2s linear infinite',
  },
  inputBar: {
    padding: '16px 24px',
    backgroundColor: 'var(--bg-surface, #0f172a)',
    borderTop: '1px solid var(--border-subtle, #1e293b)',
  },
  inputWrapper: {
    display: 'flex',
    gap: '12px',
    maxWidth: '900px',
    margin: '0 auto',
  },
  queryInput: {
    flex: 1,
    backgroundColor: '#090d16',
    border: '1px solid #334155',
    color: '#f8fafc',
    fontSize: '14px',
    padding: '12px 16px',
    borderRadius: '6px',
    outline: 'none',
  },
  sendBtn: {
    backgroundColor: '#0891b2',
    color: '#ffffff',
    border: 'none',
    borderRadius: '6px',
    padding: '0 20px',
    fontSize: '13px',
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: '0.5px',
    whiteSpace: 'nowrap',
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.75)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    width: '90%',
    maxWidth: '650px',
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
  },
  modalHeader: {
    padding: '16px 20px',
    borderBottom: '1px solid #1e293b',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    fontSize: '15px',
    fontWeight: 700,
    color: '#f8fafc',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#94a3b8',
    fontSize: '18px',
    cursor: 'pointer',
  },
  modalBody: {
    padding: '20px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  inspectorRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '13px',
    borderBottom: '1px solid #1e293b',
    paddingBottom: '8px',
  },
  inspLabel: {
    color: '#94a3b8',
    fontWeight: 600,
  },
  inspVal: {
    color: '#f8fafc',
  },
  inspValMono: {
    color: '#38bdf8',
    fontFamily: 'monospace',
    fontSize: '12px',
  },
  inspectorContentBox: {
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '12px',
    marginTop: '8px',
  },
  inspBoxLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748b',
    marginBottom: '6px',
    letterSpacing: '0.5px',
  },
  inspBoxContent: {
    fontSize: '13px',
    color: '#e2e8f0',
    lineHeight: 1.5,
  },
  inspectorReasonBox: {
    backgroundColor: '#042f2e',
    border: '1px solid #0d9488',
    borderRadius: '6px',
    padding: '12px',
  },
  inspReasonText: {
    fontSize: '12px',
    color: '#ccfbf1',
    lineHeight: 1.4,
  },
  modalFooter: {
    padding: '14px 20px',
    borderTop: '1px solid #1e293b',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  doneBtn: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    color: '#f8fafc',
    padding: '8px 16px',
    borderRadius: '4px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
  },
};

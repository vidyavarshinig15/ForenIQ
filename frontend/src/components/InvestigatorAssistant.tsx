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
    backgroundColor: '#0B1220',
    color: '#F8FAFC',
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
  header: {
    padding: '16px 24px',
    backgroundColor: '#111827',
    borderBottom: '1px solid #263449',
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
    fontSize: '24px',
    color: '#3B82F6',
  },
  headerTitle: {
    fontFamily: '"Space Grotesk", sans-serif',
    fontSize: '18px',
    fontWeight: 700,
    color: '#F8FAFC',
    margin: 0,
    letterSpacing: '-0.02em',
  },
  headerSubtitle: {
    fontSize: '12px',
    color: '#94A3B8',
    marginTop: '2px',
    fontFamily: '"IBM Plex Sans", sans-serif',
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
    backgroundColor: '#172033',
    border: '1px solid #3B82F6',
    color: '#3B82F6',
    fontSize: '11px',
    fontWeight: 700,
    padding: '6px 12px',
    borderRadius: '2px',
    fontFamily: '"IBM Plex Mono", monospace',
    letterSpacing: '0.05em',
  },
  statusDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    backgroundColor: '#10B981',
    boxShadow: '0 0 6px rgba(16, 185, 129, 0.4)',
  },
  clearBtn: {
    backgroundColor: 'transparent',
    border: '1px solid #263449',
    color: '#94A3B8',
    fontSize: '11px',
    fontWeight: 700,
    padding: '6px 12px',
    borderRadius: '2px',
    cursor: 'pointer',
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
  contentGrid: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    backgroundColor: '#0B1220',
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
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '32px',
    textAlign: 'center',
  },
  welcomeIcon: {
    fontSize: '36px',
    marginBottom: '12px',
    color: '#3B82F6',
  },
  welcomeTitle: {
    fontFamily: '"Space Grotesk", sans-serif',
    fontSize: '20px',
    fontWeight: 700,
    color: '#F8FAFC',
    marginBottom: '8px',
  },
  welcomeDesc: {
    fontSize: '14px',
    color: '#94A3B8',
    lineHeight: 1.6,
    marginBottom: '24px',
  },
  complianceNotice: {
    textAlign: 'left',
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderLeft: '3px solid #3B82F6',
    borderRadius: '2px',
    padding: '16px',
    marginBottom: '24px',
  },
  noticeHeading: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#3B82F6',
    letterSpacing: '0.05em',
    marginBottom: '8px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  noticeList: {
    fontSize: '12px',
    color: '#94A3B8',
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
    color: '#64748B',
    letterSpacing: '0.05em',
    marginBottom: '10px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  quickList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  quickBtn: {
    textAlign: 'left',
    backgroundColor: '#1E293B',
    border: '1px solid #263449',
    color: '#F8FAFC',
    padding: '10px 14px',
    borderRadius: '2px',
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
    backgroundColor: '#1E293B',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '14px 18px',
    maxWidth: '85%',
  },
  userLabelRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '10px',
    fontWeight: 700,
    color: '#22D3EE',
    marginBottom: '4px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  userAvatar: {
    fontSize: '12px',
  },
  userName: {
    letterSpacing: '0.05em',
  },
  userText: {
    fontSize: '14px',
    color: '#F8FAFC',
    lineHeight: 1.5,
  },
  assistantCard: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderLeft: '4px solid #3B82F6',
    borderRadius: '4px',
    padding: '20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  assistantHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #263449',
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
    color: '#3B82F6',
  },
  assistantName: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#3B82F6',
    letterSpacing: '0.05em',
    fontFamily: '"Space Grotesk", sans-serif',
  },
  latencyBadge: {
    fontSize: '11px',
    fontFamily: '"IBM Plex Mono", monospace',
    color: '#94A3B8',
    backgroundColor: '#111827',
    padding: '2px 6px',
    borderRadius: '2px',
    border: '1px solid #263449',
  },
  verifiedBadge: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#10B981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    padding: '3px 8px',
    borderRadius: '2px',
    border: '1px solid #10B981',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  warningBadge: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#F59E0B',
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    padding: '3px 8px',
    borderRadius: '2px',
    border: '1px solid #F59E0B',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  providerTag: {
    fontSize: '11px',
    color: '#64748B',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  planBanner: {
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '2px',
    padding: '8px 12px',
    fontSize: '11px',
    color: '#94A3B8',
    display: 'flex',
    flexWrap: 'wrap',
    gap: '12px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  planLabel: {
    fontWeight: 700,
    color: '#3B82F6',
  },
  planIntent: {
    color: '#F8FAFC',
  },
  planMode: {
    color: '#22D3EE',
  },
  planEntities: {
    color: '#F8FAFC',
  },
  answerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  sectionHeaderTitle: {
    fontSize: '11px',
    fontWeight: 700,
    color: '#64748B',
    letterSpacing: '0.05em',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  answerText: {
    fontSize: '14px',
    color: '#F8FAFC',
    lineHeight: 1.6,
  },
  answerParagraph: {
    margin: '4px 0',
  },
  inlineCitationBadge: {
    display: 'inline-block',
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    border: '1px solid #22D3EE',
    color: '#22D3EE',
    padding: '1px 6px',
    borderRadius: '2px',
    fontSize: '12px',
    fontWeight: 700,
    fontFamily: '"IBM Plex Mono", monospace',
    cursor: 'pointer',
    margin: '0 2px',
    transition: 'all 0.15s ease',
  },
  conflictBox: {
    backgroundColor: 'rgba(245, 158, 11, 0.08)',
    border: '1px solid #F59E0B',
    borderRadius: '4px',
    padding: '12px 16px',
  },
  conflictHeading: {
    fontSize: '12px',
    fontWeight: 700,
    color: '#F59E0B',
    marginBottom: '6px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  conflictItem: {
    fontSize: '12px',
    color: '#F8FAFC',
  },
  conflictField: {
    fontWeight: 600,
    color: '#F59E0B',
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
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '4px',
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
    backgroundColor: 'rgba(34, 211, 238, 0.12)',
    color: '#22D3EE',
    border: '1px solid #22D3EE',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: '"IBM Plex Mono", monospace',
    padding: '2px 6px',
    borderRadius: '2px',
  },
  citType: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#94A3B8',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  citApp: {
    fontSize: '10px',
    color: '#10B981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    border: '1px solid rgba(16, 185, 129, 0.3)',
    padding: '2px 5px',
    borderRadius: '2px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  citTime: {
    fontSize: '11px',
    color: '#64748B',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  citParties: {
    fontSize: '11px',
    color: '#94A3B8',
  },
  citSnippet: {
    fontSize: '12px',
    color: '#F8FAFC',
    fontStyle: 'italic',
    lineHeight: 1.4,
    marginTop: '4px',
  },
  citAction: {
    fontSize: '10px',
    fontWeight: 600,
    color: '#22D3EE',
    marginTop: '6px',
    textAlign: 'right',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  caveatsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '12px',
  },
  caveatCard: {
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '2px',
    padding: '10px 12px',
  },
  caveatLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#94A3B8',
    marginBottom: '4px',
    letterSpacing: '0.05em',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  caveatText: {
    fontSize: '12px',
    color: '#94A3B8',
    lineHeight: 1.4,
  },
  reproducibilityBar: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px',
    fontSize: '10px',
    color: '#64748B',
    fontFamily: '"IBM Plex Mono", monospace',
    borderTop: '1px solid #263449',
    paddingTop: '10px',
  },
  errorBox: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    border: '1px solid #EF4444',
    borderRadius: '4px',
    padding: '14px',
    color: '#EF4444',
    fontSize: '13px',
  },
  errorHeading: {
    fontWeight: 700,
    marginBottom: '4px',
    fontFamily: '"Space Grotesk", sans-serif',
  },
  loadingBox: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '4px',
    padding: '16px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    color: '#3B82F6',
    fontSize: '13px',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  loadingSpin: {
    fontSize: '18px',
    animation: 'spin 2s linear infinite',
  },
  inputBar: {
    padding: '16px 24px',
    backgroundColor: '#111827',
    borderTop: '1px solid #263449',
  },
  inputWrapper: {
    display: 'flex',
    gap: '12px',
    maxWidth: '900px',
    margin: '0 auto',
  },
  queryInput: {
    flex: 1,
    backgroundColor: '#111827',
    border: '1px solid #263449',
    color: '#F8FAFC',
    fontSize: '14px',
    padding: '12px 16px',
    borderRadius: '2px',
    outline: 'none',
    fontFamily: '"IBM Plex Sans", sans-serif',
  },
  sendBtn: {
    backgroundColor: '#22D3EE',
    color: '#0B1220',
    border: 'none',
    borderRadius: '2px',
    padding: '0 20px',
    fontSize: '13px',
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: '0.05em',
    whiteSpace: 'nowrap',
    fontFamily: '"Space Grotesk", sans-serif',
  },
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(11, 18, 32, 0.85)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    backgroundColor: '#172033',
    border: '1px solid #263449',
    borderRadius: '4px',
    width: '90%',
    maxWidth: '650px',
    maxHeight: '85vh',
    display: 'flex',
    flexDirection: 'column',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
  },
  modalHeader: {
    padding: '16px 20px',
    borderBottom: '1px solid #263449',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalTitle: {
    fontFamily: '"Space Grotesk", sans-serif',
    fontSize: '15px',
    fontWeight: 700,
    color: '#F8FAFC',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#94A3B8',
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
    borderBottom: '1px solid #263449',
    paddingBottom: '8px',
  },
  inspLabel: {
    color: '#94A3B8',
    fontWeight: 600,
  },
  inspVal: {
    color: '#F8FAFC',
  },
  inspValMono: {
    color: '#22D3EE',
    fontFamily: '"IBM Plex Mono", monospace',
    fontSize: '12px',
  },
  inspectorContentBox: {
    backgroundColor: '#111827',
    border: '1px solid #263449',
    borderRadius: '2px',
    padding: '12px',
    marginTop: '8px',
  },
  inspBoxLabel: {
    fontSize: '10px',
    fontWeight: 700,
    color: '#64748B',
    marginBottom: '6px',
    letterSpacing: '0.05em',
    fontFamily: '"IBM Plex Mono", monospace',
  },
  inspBoxContent: {
    fontSize: '13px',
    color: '#F8FAFC',
    lineHeight: 1.5,
  },
  inspectorReasonBox: {
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    border: '1px solid #3B82F6',
    borderRadius: '2px',
    padding: '12px',
  },
  inspReasonText: {
    fontSize: '12px',
    color: '#F8FAFC',
    lineHeight: 1.4,
  },
  modalFooter: {
    padding: '14px 20px',
    borderTop: '1px solid #263449',
    display: 'flex',
    justifyContent: 'flex-end',
  },
  doneBtn: {
    backgroundColor: '#1E293B',
    border: '1px solid #263449',
    color: '#F8FAFC',
    padding: '8px 16px',
    borderRadius: '2px',
    fontSize: '12px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: '"Space Grotesk", sans-serif',
  },
};

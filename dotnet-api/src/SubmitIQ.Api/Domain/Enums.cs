namespace SubmitIQ.Api.Domain;

// Stored as strings so the database stays readable and survives enum reordering.

public enum SubmissionStatus { NeedsReview, AutoCleared, Approved, Failed }

/// <summary>Mirrors the Python pipeline's FieldProvenance.status values.</summary>
public enum FieldStatus { Ok, LowConfidence, Conflict, Invalid, Missing }

public enum DecisionOutcome { Accept, Refer, Decline }

public enum ReviewTaskStatus { Open, Resolved }

public enum ReviewResolution { Confirmed, Corrected }

public enum AuditEventType { SubmissionIngested, FieldConfirmed, FieldCorrected, DecisionMade }

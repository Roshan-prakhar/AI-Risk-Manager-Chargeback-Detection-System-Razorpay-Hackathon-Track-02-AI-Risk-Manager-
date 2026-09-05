package com.fraudguard.evidence.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.Instant;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "evidence_snapshots")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class EvidenceSnapshot {

    @Id
    private Long transactionId;

    @Column(columnDefinition = "CLOB")
    private String featureSnapshotJson;

    private double gbtScore;

    private String tier;

    @Enumerated(EnumType.STRING)
    @Builder.Default
    private DeliveryStatus deliveryStatus = DeliveryStatus.PENDING;

    private Instant deliveryConfirmedAt;

    private Instant cachedAt;

    @PrePersist
    public void prePersist() {
        if (this.cachedAt == null) {
            this.cachedAt = Instant.now();
        }
    }
}

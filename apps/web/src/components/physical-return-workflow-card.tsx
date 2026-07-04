import styles from "./physical-return-workflow-card.module.css";

type PhysicalReturnWorkflowCardProps = Readonly<{
  acceptedByCourierAt: string;
  acceptedByCourierComplete: boolean;
  isConfirmingCarrierAcceptance?: boolean;
  labelCreatedAt: string;
  onConfirmCarrierAcceptance?: () => void;
  returnRequestedAt: string;
}>;

export function PhysicalReturnWorkflowCard({
  acceptedByCourierAt,
  acceptedByCourierComplete,
  isConfirmingCarrierAcceptance = false,
  labelCreatedAt,
  onConfirmCarrierAcceptance,
  returnRequestedAt,
}: PhysicalReturnWorkflowCardProps) {
  const steps = [
    {
      label: "Return Requested",
      state: "complete",
      value: returnRequestedAt,
    },
    {
      label: "Label Created",
      state: "complete",
      value: labelCreatedAt,
    },
    {
      label: "Accepted by Courier",
      state: acceptedByCourierComplete ? "complete" : "active",
      value: acceptedByCourierAt,
    },
  ] as const;

  return (
    <section className={styles.card} aria-label="Physical return workflow">
      {steps.map((step) => {
        const isCarrierAcceptanceStep = step.label === "Accepted by Courier";
        const showCarrierAcceptanceButton =
          isCarrierAcceptanceStep && !acceptedByCourierComplete;

        return (
          <div key={step.label}>
            <span
              className={styles.marker}
              role="img"
              aria-label={`${step.label} ${step.state}`}
            >
              {step.state === "complete" ? (
                <span className={styles.completeMark} aria-hidden="true">
                  ✓
                </span>
              ) : (
                <span className={styles.activeDot} aria-hidden="true" />
              )}
            </span>
            <p>{step.label}</p>
            {showCarrierAcceptanceButton ? null : <p>{step.value}</p>}
            {showCarrierAcceptanceButton ? (
              <button
                className={styles.actionButton}
                disabled={isConfirmingCarrierAcceptance}
                onClick={onConfirmCarrierAcceptance}
                type="button"
              >
                Given to Carrier
              </button>
            ) : null}
          </div>
        );
      })}
    </section>
  );
}

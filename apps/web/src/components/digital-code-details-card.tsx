import styles from "./digital-code-details-card.module.css";

type DigitalCodeDetailsCardProps = Readonly<{
  codeRedeemed: boolean;
  isMuted?: boolean;
  issuedCode: string;
}>;

export function DigitalCodeDetailsCard({
  codeRedeemed,
  isMuted = false,
  issuedCode,
}: DigitalCodeDetailsCardProps) {
  return (
    <section
      className={`${styles.card} ${isMuted ? styles.muted : ""}`}
      aria-label="Digital code details"
    >
      <div>
        <p>Issued Code</p>
        <p>{issuedCode}</p>
      </div>
      <div>
        <p>Redeemed State</p>
        <p>{codeRedeemed ? "Redeemed" : "Not redeemed"}</p>
      </div>
    </section>
  );
}

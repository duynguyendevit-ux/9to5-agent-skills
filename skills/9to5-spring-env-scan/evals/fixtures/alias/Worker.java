class Worker {
    @Value("${worker.effective-timeout}")
    String timeout;
    String region = System.getenv("REGION");
    // System.getenv("COMMENT_ONLY");
}

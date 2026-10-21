#include <sai.h>
#include <cstdio>

int main() {
    void *methods = nullptr;
    if (sai_api_query(SAI_API_SWITCH, &methods) != SAI_STATUS_SUCCESS || !methods)
        return 1;
    std::puts("DASH installed SDK API query passed");
    return 0;
}
